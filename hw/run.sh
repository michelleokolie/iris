#!/bin/sh
# Start the whole pipeline and keep it alive:  sudo sh hw/run.sh        (Ctrl-C or SIGTERM stops it)
#
# Starts io (python3 hw/io_main.py), then vision (waits for io's socket first), then the ultrasonic reader.
# Each one runs in its own restart loop: when it exits, wait 1 s and start it again. A process that exits more
# than MAX_EXITS times within WINDOW_S is broken: the whole system is stopped and this script exits 1.
# The programs themselves never respawn anything (they crash loudly); supervision lives only here.
#
# Needs (build on the Pi, see hw/README.md): hw/accel, hw/ultrasonic, vision/vision, and the model file.
# Environment: IRIS_MODEL (model path), IRIS_SOCK (default /tmp/iris.sock), IRIS_LOGDIR (default /tmp/iris).
# Logs: $IRIS_LOGDIR/io.log, vision.log, ultrasonic.log (truncated at start, appended across restarts).
#
# Stopping: io gets SIGINT (it switches the outputs off and exits); vision and the reader get SIGTERM (vision has
# no signal handler and is started with SIGINT ignored, because a shell ignores SIGINT for background jobs; the
# reader handles SIGTERM like SIGINT). Every stop WAITS. Never SIGKILL the reader: it must run rpi_gpio_cleanup().
# Plain POSIX sh, LF line endings only.

HW=$(cd "$(dirname "$0")" && pwd)
ROOT=$(dirname "$HW")
MODEL=${IRIS_MODEL:-/data/home/qnxuser/capture/deimv2_femto.onnx}
SOCK=${IRIS_SOCK:-/tmp/iris.sock}
LOGDIR=${IRIS_LOGDIR:-/tmp/iris}
RESTART_WAIT_S=1
WINDOW_S=30
MAX_EXITS=5

for f in "$HW/accel" "$HW/ultrasonic" "$ROOT/vision/vision"; do
    [ -x "$f" ] || { echo "run.sh: $f is missing or not executable; build it first (hw/README.md)" >&2; exit 2; }
done
for f in "$HW/io_main.py" "$MODEL"; do
    [ -f "$f" ] || { echo "run.sh: $f not found (the model path can be set with IRIS_MODEL)" >&2; exit 2; }
done

# supervise NAME SIGNAL COMMAND...  (runs as a background subshell)
supervise() {
    name=$1; sig=$2; shift 2
    stopping=0
    child=
    trap 'stopping=1; [ -n "$child" ] && kill -$sig "$child"' TERM
    exits=
    while [ "$stopping" = 0 ]; do
        if [ "$name" != io ]; then  # clients connect to io's socket, which exists only while io is up
            while [ ! -S "$SOCK" ] && [ "$stopping" = 0 ]; do sleep 1; done
            [ "$stopping" = 0 ] || break
        fi
        "$@" >>"$LOGDIR/$name.log" 2>&1 &
        child=$!
        echo "run.sh: $name started (pid $child)"
        rc=?
        while kill -0 "$child" 2>/dev/null; do  # a trapped TERM interrupts wait; keep waiting for the real exit
            wait "$child"
            rc=$?
        done
        child=
        [ "$name" != io ] || rm -f "$SOCK"  # a dead io leaves its socket file behind; clients must not connect to it
        [ "$stopping" = 0 ] || break
        echo "run.sh: $name exited (status $rc)"
        now=$(date +%s)
        recent=
        n=0
        for t in $exits $now; do
            if [ $((now - t)) -le "$WINDOW_S" ]; then recent="$recent $t"; n=$((n + 1)); fi
        done
        exits=$recent
        if [ "$n" -gt "$MAX_EXITS" ]; then
            echo "run.sh: FAULT: $name exited $n times within ${WINDOW_S}s, giving up and stopping everything (see $LOGDIR/$name.log)"
            echo "$name" >"$LOGDIR/fault"
            kill -TERM $$
            exit 1
        fi
        echo "run.sh: restarting $name in ${RESTART_WAIT_S}s"
        sleep "$RESTART_WAIT_S"
    done
}

stop_all() {
    trap '' INT TERM  # a second Ctrl-C while stopping does nothing; the stops below wait for the programs
    echo "run.sh: stopping, waiting for each program to exit"
    kill -TERM "$US_PID" "$VISION_PID" "$IO_PID" 2>/dev/null
    wait "$US_PID"
    wait "$VISION_PID"
    wait "$IO_PID"
    echo "run.sh: stopped"
    [ ! -f "$LOGDIR/fault" ] || exit 1
    exit 0
}

mkdir -p "$LOGDIR"
rm -f "$LOGDIR/fault" "$SOCK"
: >"$LOGDIR/io.log"
: >"$LOGDIR/vision.log"
: >"$LOGDIR/ultrasonic.log"

IO_PID=
VISION_PID=
US_PID=
trap stop_all INT TERM

supervise io INT python3 "$HW/io_main.py" --socket "$SOCK" &
IO_PID=$!
supervise vision TERM "$ROOT/vision/vision" "$MODEL" "$SOCK" &
VISION_PID=$!
supervise ultrasonic TERM "$HW/ultrasonic" "$SOCK" &
US_PID=$!
echo "run.sh: running; logs in $LOGDIR; Ctrl-C to stop"
wait
