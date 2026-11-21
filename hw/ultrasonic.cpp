// HC-SR04 reader for QNX (Pi 5). Event-driven like QNX's own sample
// (qnx/Raspberry-Pi-Hardware-Component-Samples, hc-sr04_ultrasonic_sensor/c): rpi_gpio sends a
// pulse to a QNX channel on each echo edge, so there is no busy-wait and no GIL contention
// with io. Same filtering as hw/ultrasonic.py: median of 3, closing speed over the last 7.
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
#include <cerrno>
#include <csignal>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <ctime>
#include <deque>
#include <string>
#include <utility>

extern "C" {
#include "rpi_gpio.h"  // QNX inline GPIO functions
}

static constexpr double CM_PER_US = 0.0343 / 2.0;     // speed of sound, halved for the round trip
static constexpr uint64_t EDGE_TIMEOUT_NS = 30'000'000;  // ~5 m round trip
static constexpr double PERIOD_S = 0.060;             // HC-SR04 needs ~60 ms between pings
static constexpr size_t FILTER_SIZE = 3;
static constexpr size_t WINDOW_SIZE = 7;
static constexpr int EVENT_ECHO = 1;

static volatile sig_atomic_t running = 1;
static int chid;

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
    return (now_s() - t_rise) * 1e6 * CM_PER_US;
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
    std::deque<double> raw;
    std::deque<std::pair<double, double>> history;  // (time_s, filtered_cm)

    while (running) {
        double t0 = now_s();
        double cm = read_cm(trig);
        if (cm < 0) {
            raw.clear();
            history.clear();  // don't compute speed across a gap
            send_line(fd, "range none\n");
        } else {
            raw.push_back(cm);
            if (raw.size() > FILTER_SIZE) raw.pop_front();
            if (raw.size() == FILTER_SIZE) {
                std::deque<double> sorted(raw);
                std::sort(sorted.begin(), sorted.end());
                history.emplace_back(now_s(), sorted[FILTER_SIZE / 2]);
                if (history.size() > WINDOW_SIZE) history.pop_front();
                auto [t_old, d_old] = history.front();
                auto [t_new, d_new] = history.back();
                double closing = t_new > t_old ? (d_old - d_new) / (t_new - t_old) : 0.0;
                char line[64];
                std::snprintf(line, sizeof(line), "range %.1f %.1f\n", d_new, closing);
                send_line(fd, line);
            }
        }
        double rest = PERIOD_S - (now_s() - t0);
        if (rest > 0) usleep(static_cast<useconds_t>(rest * 1e6));
    }
    check(rpi_gpio_cleanup(), "cleanup");
    return 0;
}
