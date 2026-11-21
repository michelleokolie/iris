// HC-SR04 reader for QNX (Pi 5). Event-driven like QNX's own sample
// (qnx/Raspberry-Pi-Hardware-Component-Samples, hc-sr04_ultrasonic_sensor/c): rpi_gpio sends a
// pulse to a QNX channel on each echo edge, so there is no busy-wait and no GIL contention
// with io. Filtering: jump rejection, median of 3, closing speed = least-squares slope over the last 7.
//
// Sends to io over the UNIX socket, one line per measurement (docs/interfaces.md):
//   "range <cm> <closing_cm_per_s>\n"   closing > 0 = getting closer
//   "range none\n"                      no echo in time
//
// Usage (root, io must be listening): sudo ./ultrasonic [socket_path] [trig_gpio] [echo_gpio]
// Build: see docs/decisions.md (needs QNX's common/rpi_gpio built on the board).

#include <sys/iomsg.h>
#include <sys/mman.h>
#include <sys/neutrino.h>
#include <sys/socket.h>
#include <sys/un.h>
#include <unistd.h>

#include <algorithm>
#include <cassert>
#include <cmath>
#include <cerrno>
#include <csignal>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <ctime>
#include <deque>
#include <optional>
#include <string>
#include <utility>

extern "C" {
#include "rpi_gpio.h"  // QNX inline GPIO functions
}

static constexpr double CM_PER_US = 0.0343 / 2.0;     // speed of sound, halved for the round trip
static constexpr uint64_t EDGE_TIMEOUT_NS = 30'000'000;  // ~5 m round trip
static constexpr double MIN_PULSE_US = 120;           // ~2 cm, the HC-SR04's minimum range: a shorter pulse is a glitch
static constexpr double PERIOD_S = 0.060;             // HC-SR04 needs ~60 ms between pings
static constexpr size_t FILTER_SIZE = 3;
static constexpr size_t WINDOW_SIZE = 7;
static constexpr size_t MIN_SLOPE_POINTS = 3;         // no closing speed until the window holds this many
static constexpr double JUMP_CM = 50;                 // a reading this far from the last accepted one needs confirming
static constexpr double CONFIRM_CM = 15;              // ...by the next reading agreeing within this
static constexpr double MAX_CLOSING = 300;            // cm/s; walking is ~140
static constexpr int EVENT_ECHO = 1;

static volatile sig_atomic_t running = 1;
static int chid;

// --- range filter (pure; compiled on its own by the scratch checks) ---
struct Output { double cm, closing; };

// Closing speed (cm/s, > 0 = getting closer) from (time_s, cm) points: negated least-squares slope, clamped.
static double closing_speed(const std::deque<std::pair<double, double>>& pts) {
    if (pts.size() < MIN_SLOPE_POINTS) return 0.0;
    double n = static_cast<double>(pts.size()), st = 0, sd = 0;
    for (auto [t, d] : pts) { st += t; sd += d; }
    double mt = st / n, md = sd / n, num = 0, den = 0;
    for (auto [t, d] : pts) { num += (t - mt) * (d - md); den += (t - mt) * (t - mt); }
    return std::clamp(-num / den, -MAX_CLOSING, MAX_CLOSING);
}

class RangeFilter {
public:
    // One raw reading; an Output when there is a value to send, nothing while a jump awaits confirmation
    // or the median has fewer than FILTER_SIZE readings.
    std::optional<Output> update(double t, double cm) {
        if (accepted_ && std::abs(cm - *accepted_) > JUMP_CM) {
            bool confirmed = pending_ && std::abs(cm - *pending_) <= CONFIRM_CM;
            if (!confirmed) {
                pending_ = cm;
                return std::nullopt;
            }
            raw_.clear();  // the new surface starts a new window
            history_.clear();
            raw_.push_back(*pending_);
        }
        pending_.reset();
        accepted_ = cm;
        raw_.push_back(cm);
        if (raw_.size() > FILTER_SIZE) raw_.pop_front();
        if (raw_.size() < FILTER_SIZE) return std::nullopt;
        std::deque<double> sorted(raw_);
        std::sort(sorted.begin(), sorted.end());
        double median = sorted[FILTER_SIZE / 2];
        history_.emplace_back(t, median);
        if (history_.size() > WINDOW_SIZE) history_.pop_front();
        return Output{median, closing_speed(history_)};
    }
    // No echo: the next readings start a new window (the jump reference stays: a gap is not a new target).
    void gap() {
        raw_.clear();
        history_.clear();
    }

private:
    std::deque<double> raw_;
    std::deque<std::pair<double, double>> history_;  // (time_s, median_cm)
    std::optional<double> accepted_;                 // last accepted raw reading
    std::optional<double> pending_;                  // an unconfirmed jump
};
// --- end range filter ---

static void check(int rc, const char* what) {
    if (rc != 0) {
        std::perror(what);
        std::exit(1);
    }
}

static double now_s() {
    timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return ts.tv_sec + ts.tv_nsec / 1e9;
}

// Block for the next echo edge pulse; false on timeout.
static bool wait_edge(uint64_t timeout_ns) {
    uint64_t to = timeout_ns;
    TimerTimeout(CLOCK_MONOTONIC, _NTO_TIMEOUT_RECEIVE, nullptr, &to, nullptr);
    _pulse pulse;
    if (MsgReceivePulse(chid, &pulse, sizeof(pulse), nullptr) == -1) {
        assert(errno == ETIMEDOUT || errno == EINTR);
        return false;
    }
    assert(pulse.code == _PULSE_CODE_MINAVAIL && pulse.value.sival_int == EVENT_ECHO);
    return true;
}

// One raw reading in cm, or -1 if the echo didn't come back.
static double read_cm(int trig) {
    while (wait_edge(1)) {}  // drop stale edges from a previous ping
    check(rpi_gpio_output(trig, GPIO_HIGH), "trigger high");
    timespec ten_us{0, 10 * 1000};
    nanosleep(&ten_us, nullptr);
    check(rpi_gpio_output(trig, GPIO_LOW), "trigger low");

    if (!wait_edge(EDGE_TIMEOUT_NS)) return -1;  // rising
    double t_rise = now_s();
    if (!wait_edge(EDGE_TIMEOUT_NS)) return -1;  // falling
    double pulse_us = (now_s() - t_rise) * 1e6;
    if (pulse_us < MIN_PULSE_US) return -1;  // a near-zero edge pair is not an echo ("range none", never "range 0.0")
    return pulse_us * CM_PER_US;
}

static int connect_io(const char* path) {
    int fd = socket(AF_UNIX, SOCK_STREAM, 0);
    sockaddr_un addr{};
    addr.sun_family = AF_UNIX;
    std::strncpy(addr.sun_path, path, sizeof(addr.sun_path) - 1);
    if (fd < 0 || connect(fd, reinterpret_cast<sockaddr*>(&addr), sizeof(addr)) != 0) {
        std::perror(path);
        std::exit(1);
    }
    return fd;
}

// write() may send less than asked or be interrupted by a signal; a truncated line would
// corrupt the stream, so loop until the whole line is out.
static void send_line(int fd, const std::string& line) {
    size_t sent = 0;
    while (sent < line.size()) {
        ssize_t n = write(fd, line.data() + sent, line.size() - sent);
        if (n < 0 && errno == EINTR) continue;
        if (n < 0) {
            std::perror("write to io");
            std::exit(1);
        }
        sent += static_cast<size_t>(n);
    }
}

int main(int argc, char** argv) {
    const char* path = argc > 1 ? argv[1] : "/tmp/iris.sock";
    const int trig = argc > 2 ? std::atoi(argv[2]) : 25;
    const int echo = argc > 3 ? std::atoi(argv[3]) : 16;

    struct sigaction sa{};
    sa.sa_handler = [](int) { running = 0; };
    sigaction(SIGINT, &sa, nullptr);
    sigaction(SIGTERM, &sa, nullptr);

    chid = ChannelCreate(_NTO_CHF_PRIVATE);
    assert(chid != -1);
    int coid = ConnectAttach(0, 0, chid, _NTO_SIDE_CHANNEL, 0);
    assert(coid != -1);
    check(rpi_gpio_setup(trig, GPIO_OUT), "setup trig");
    check(rpi_gpio_setup_pull(echo, GPIO_IN, GPIO_PUD_OFF), "setup echo");
    check(rpi_gpio_add_event_detect(echo, coid, GPIO_RISING | GPIO_FALLING, EVENT_ECHO), "event detect");
    check(rpi_gpio_output(trig, GPIO_LOW), "trigger low");
    sleep(1);  // let the sensor settle

    int fd = connect_io(path);
    RangeFilter filter;

    while (running) {
        double t0 = now_s();
        double cm = read_cm(trig);
        if (cm < 0) {
            filter.gap();
            send_line(fd, "range none\n");
        } else if (auto out = filter.update(now_s(), cm)) {
            char line[64];
            std::snprintf(line, sizeof(line), "range %.1f %.1f\n", out->cm, out->closing);
            send_line(fd, line);
        }
        double rest = PERIOD_S - (now_s() - t0);
        if (rest > 0) usleep(static_cast<useconds_t>(rest * 1e6));
    }
    check(rpi_gpio_cleanup(), "cleanup");
    return 0;
}
