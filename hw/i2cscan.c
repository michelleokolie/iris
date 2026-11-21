// usage: i2cscan /dev/i2c1  -- reports every 7-bit address that ACKs a 1-byte read
#include <fcntl.h>
#include <stdio.h>
#include <stdint.h>
#include <devctl.h>
#include <hw/i2c.h>

int main(int argc, char **argv)
    if (argc != 2) {
        fprintf(stderr, "usage: i2cscan /dev/i2c1\n");
        return 2;
    }
    int fd = open(argv[1], O_RDWR);
    if (fd < 0) { perror("open"); return 1; }
    for (unsigned a = 0x08; a <= 0x77; a++) {
        struct { i2c_recv_t hdr; uint8_t data[1]; } r = {
            .hdr = { .slave = { .addr = a, .fmt = I2C_ADDRFMT_7BIT }, .len = 1, .stop = 1 } };
        if (devctl(fd, DCMD_I2C_RECV, &r, sizeof(r), NULL) == 0)
            printf("found 0x%02x\n", a);
    }
    return 0;
}
