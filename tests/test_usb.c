/* Transport control-path test using a mock kernel; no UDC is used. */
#include <stdarg.h>
#include <assert.h>
#include <sys/ioctl.h>
#include <linux/usb/raw_gadget.h>
#include <string.h>
static unsigned long last_op;
static unsigned char transferred[256];
static size_t transferred_n;
static int stalled;
int mock_ioctl(int fd,unsigned long op,...) {
    (void)fd;va_list ap;va_start(ap,op);void *arg=va_arg(ap,void *);va_end(ap);last_op=op;
    if(op==USB_RAW_IOCTL_EP0_WRITE || op==USB_RAW_IOCTL_EP0_READ) {
        struct usb_raw_ep_io *io=arg;transferred_n=io->length;
        if(op==USB_RAW_IOCTL_EP0_READ && io->length==3) memcpy(io->data,"Q\x10\x04",3);
        if(io->length) memcpy(transferred,io->data,io->length);
        return (int)io->length;
    }
    if(op==USB_RAW_IOCTL_EP0_STALL) stalled++;
    return 0;
}
#define ioctl mock_ioctl
#define main bridge_main
#include "../usb/raw_bridge.c"
#undef main
#undef ioctl
static void request(uint8_t type,uint8_t req,uint16_t value,uint16_t index,uint16_t n) {
    struct usb_ctrlrequest c={.bRequestType=type,.bRequest=req,.wValue=htole16(value),.wIndex=htole16(index),.wLength=htole16(n)};
    control(c);
}
int main(void) {
    request(0x80,6,0x0100,0,18);assert(transferred_n==18);assert(!memcmp(transferred,device_desc,18));
    request(0x80,6,0x0200,0,255);assert(transferred_n==41);assert(!memcmp(transferred,config_desc,41));
    request(0x81,6,0x2200,0,255);assert(transferred_n==29);assert(!memcmp(transferred,report_desc,29));
    request(0x80,6,0x0302,0x409,255);assert(transferred_n==24);assert(transferred[0]==24);
    request(0x80,6,0x0303,0x409,255);assert(last_op==USB_RAW_IOCTL_EP0_STALL);
    request(0x21,10,0x0700,0,0);request(0xa1,2,0,0,1);assert(transferred[0]==7);
    request(0x21,11,0,0,0);request(0xa1,3,0,0,1);assert(transferred[0]==0);
    request(0xa1,1,0x0100,0,32);assert(transferred_n==0);
    int pipes[2];assert(pipe(pipes)==0);int old_stdout=dup(1);assert(dup2(pipes[1],1)>=0);
    request(0x21,9,0x0200,0,3);
    unsigned char packet[5];assert(read(pipes[0],packet,5)==5);assert(!memcmp(packet,"\x01\x03Q\x10\x04",5));
    assert(dup2(old_stdout,1)>=0);close(old_stdout);close(pipes[0]);close(pipes[1]);
    int old_stalled=stalled;request(0x21,9,0x0200,0,65);assert(stalled==old_stalled+1);
    puts("USB control-path mock checks passed");return 0;
}
