// usage: accel /dev/i2c1 [hz]  -- MMA7660FC at 0x4C; prints "x y z" raw 6-bit signed counts, one line per sample
#include <fcntl.h>
#include <stdio.h>
#include <stdint.h>
#include <stdlib.h>
#include <unistd.h>
#include <errno.h>
#include <devctl.h>
#include <hw/i2c.h>

#define ADDR 0x4C
#define REG_MODE 0x07
#define INVALID 0x40

static int fd;

static void write_reg(uint8_t reg, uint8_t val)
{
    struct { i2c_send_t hdr; uint8_t data[2]; } s = {
        .hdr = { .slave = { .addr = ADDR, .fmt = I2C_ADDRFMT_7BIT }, .len = 2, .stop = 1 },
        .data = { reg, val } };
    if (devctl(fd, DCMD_I2C_SEND, &s, sizeof(s), NULL) != 0) { perror("send"); exit(1); }
}

static void read_xyz(uint8_t out[3])
{
    struct { i2c_sendrecv_t hdr; uint8_t data[4]; } r = {
        .hdr = { .slave = { .addr = ADDR, .fmt = I2C_ADDRFMT_7BIT }, .send_len = 1, .recv_len = 3, .stop = 1 },
        .data = { 0x00, 0, 0, 0 } };
    if (devctl(fd, DCMD_I2C_SENDRECV, &r, sizeof(r), NULL) != 0) { perror("sendrecv"); exit(1); }
    // devctl returns the received bytes from the START of the buffer, over the byte we sent
    // (data[1..3] was off by one: it printed Y, Z and a constant 0 as x, y, z).
    for (int i = 0; i < 3; i++) out[i] = r.data[i];
}

int main(int argc, char **argv)
{
    if (argc < 2 || argc > 3) {
        fprintf(stderr, "usage: accel /dev/i2c1 [hz]\n");
        return 1;
    }
    char *end;
    errno = 0;
    long hz = argc > 2 ? strtol(argv[2], &end, 10) : 50;
    if (argc > 2 && (*argv[2] == '\0' || *end != '\0' || errno == ERANGE || hz <= 0)) {
        fprintf(stderr, "hz must be a positive integer\n");
        return 1;
    }
    fd = open(argv[1], O_RDWR);
    if (fd < 0) { perror("open"); return 1; }
    write_reg(REG_MODE, 0x01);
    usleep(100000);  // the first read straight after waking the chip returns 0 0 0, before any conversion
    for (;;) {
        uint8_t b[3];
        do read_xyz(b); while ((b[0] | b[1] | b[2]) & INVALID);   // bit6 set = read raced an update; retry
        printf("%u %u %u\n", (unsigned)b[0], (unsigned)b[1], (unsigned)b[2]);
        fflush(stdout);
        usleep(1000000 / hz);
    }
}
