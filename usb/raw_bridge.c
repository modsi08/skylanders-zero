/* SPDX-License-Identifier: GPL-3.0-or-later
 * Raw Gadget transport. Python owns portal state; this process owns USB.
 * stdout frames: type,length,payload. 1=ep0 OUT,2=interrupt OUT,
 * 3=configured,4=IN completion. stdin consists of 32-byte IN reports.
 * Reset/deconfigure/disconnect exits; the Python supervisor rebinds.
 */
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <string.h>
#include <unistd.h>
#include <fcntl.h>
#include <errno.h>
#include <pthread.h>
#include <sys/ioctl.h>
#include <endian.h>
#include <linux/usb/raw_gadget.h>
#include "descriptors.h"
static int fd, in_ep, out_ep, configured;
static uint8_t idle, protocol=1;
static pthread_mutex_t output_lock=PTHREAD_MUTEX_INITIALIZER;
static void fail(const char *s) {perror(s); exit(1);}
static int checked(unsigned long op, void *p) {int r=ioctl(fd,op,p); if(r<0) fail("raw ioctl"); return r;}
static void frame(uint8_t type,const void *data,uint8_t n) {
    uint8_t buf[66]={type,n}; if(n) memcpy(buf+2,data,n);
    pthread_mutex_lock(&output_lock);
    size_t pos=0; while(pos<(size_t)n+2) {ssize_t k=write(1,buf+pos,n+2-pos); if(k<0 && errno==EINTR) continue; if(k<=0) fail("stdout"); pos+=(size_t)k;}
    pthread_mutex_unlock(&output_lock);
}
static int transfer(unsigned long op,int ep,void *data,size_t n) {
    struct usb_raw_ep_io *io=calloc(1,sizeof(*io)+n);
    if(!io) fail("calloc");
    io->ep=(uint16_t)ep; io->length=(uint32_t)n;
    if(n) memcpy(io->data,data,n);
    int r=ioctl(fd,op,io);
    if(r>=0 && (op==USB_RAW_IOCTL_EP_READ || op==USB_RAW_IOCTL_EP0_READ)) memcpy(data,io->data,(size_t)r);
    free(io); if(r<0) fail("USB transfer (reset/disconnect?)"); return r;
}
static void *read_out(void *unused) {
    (void)unused; uint8_t b[64];
    for(;;) {int n=transfer(USB_RAW_IOCTL_EP_READ,out_ep,b,sizeof(b)); if(n) frame(2,b,(uint8_t)n);}
    return NULL;
}
static void *write_in(void *unused) {
    (void)unused; uint8_t b[32];
    for(;;) {
        size_t pos=0;
        while(pos<sizeof(b)) {ssize_t n=read(0,b+pos,sizeof(b)-pos); if(n<0 && errno==EINTR) continue; if(n<=0) exit(0); pos+=(size_t)n;}
        transfer(USB_RAW_IOCTL_EP_WRITE,in_ep,b,sizeof(b)); frame(4,NULL,0);
    }
    return NULL;
}
static void configure(void) {
    if(configured) return;
    struct usb_endpoint_descriptor ep={.bLength=7,.bDescriptorType=5,.bEndpointAddress=0x81,.bmAttributes=3,.wMaxPacketSize=htole16(64),.bInterval=1};
    in_ep=checked(USB_RAW_IOCTL_EP_ENABLE,&ep);
    ep.bEndpointAddress=2; out_ep=checked(USB_RAW_IOCTL_EP_ENABLE,&ep);
    checked(USB_RAW_IOCTL_VBUS_DRAW,(void *)(uintptr_t)250);
    checked(USB_RAW_IOCTL_CONFIGURE,NULL); configured=1;
}
static void control(struct usb_ctrlrequest c) {
    uint16_t value=le16toh(c.wValue),index=le16toh(c.wIndex),length=le16toh(c.wLength);
    uint8_t b[256]={0}; const void *src=b; size_t n=0; int valid=1;
    fprintf(stderr,"SETUP %02x %02x %04x %04x %u\n",c.bRequestType,c.bRequest,value,index,length);
    if(c.bRequest==6 && (c.bRequestType==0x80 || c.bRequestType==0x81)) {
        switch(value>>8) {
        case 1: if((value&255)!=0) {valid=0;break;} src=device_desc;n=sizeof(device_desc);break;
        case 2: if((value&255)!=0) {valid=0;break;} src=config_desc;n=sizeof(config_desc);break;
        case 0x21: src=config_desc+18;n=9;break;
        case 0x22: src=report_desc;n=sizeof(report_desc);break;
        case 3: {
            const char *s=NULL;
            if((value&255)==0) {b[0]=4;b[1]=3;b[2]=9;b[3]=4;n=4;break;}
            if((value&255)==1) s="Activision";
            if((value&255)==2) s="Spyro Porta";
            if(!s) {valid=0;break;}
            n=2+strlen(s)*2;b[0]=(uint8_t)n;b[1]=3;
            for(size_t i=0;i<strlen(s);i++) b[2+2*i]=(uint8_t)s[i];
            break;
        }
        default: valid=0;
        }
    } else if(c.bRequestType==0 && c.bRequest==9 && length==0 && value<=1) {
        if(!value && configured) exit(0);
        if(value) configure();
        transfer(USB_RAW_IOCTL_EP0_READ,0,b,0);
        if(value) {
            /* Start workers only once, after SET_CONFIGURATION status stage. */
            static int started=0;
            if(!started) {pthread_t t;started=1;frame(3,NULL,0);if(pthread_create(&t,NULL,read_out,NULL)) exit(1);pthread_detach(t);if(pthread_create(&t,NULL,write_in,NULL)) exit(1);pthread_detach(t);}
        }
        return;
    } else if(c.bRequestType==0x80 && c.bRequest==8) {b[0]=(uint8_t)configured;n=1;
    } else if((c.bRequestType==0x80 || c.bRequestType==0x81 || c.bRequestType==0x82) && c.bRequest==0) {n=2;
    } else if(c.bRequestType==0x81 && c.bRequest==10 && index==0) {n=1;
    } else if(c.bRequestType==1 && c.bRequest==11 && index==0 && value==0 && !length) {n=0;
    } else if(c.bRequestType==0x21 && c.bRequest==9 && index==0 && (value>>8)==2 && (value&255)==0 && length<=64) {
        int got=transfer(USB_RAW_IOCTL_EP0_READ,0,b,length);if(got) frame(1,b,(uint8_t)got);return;
    } else if(c.bRequestType==0x21 && c.bRequest==10 && index==0 && !length) {idle=(uint8_t)(value>>8);
    } else if(c.bRequestType==0xa1 && c.bRequest==2 && index==0) {b[0]=idle;n=1;
    } else if(c.bRequestType==0x21 && c.bRequest==11 && index==0 && value<=1 && !length) {protocol=(uint8_t)value;
    } else if(c.bRequestType==0xa1 && c.bRequest==3 && index==0) {b[0]=protocol;n=1;
    } else if(c.bRequestType==0xa1 && c.bRequest==1 && index==0) {n=0; /* Reference returns empty GET_REPORT. */
    } else if(c.bRequestType==2 && c.bRequest==1 && value==0 && !length && configured && (index==0x81 || index==2)) {
        checked(USB_RAW_IOCTL_EP_CLEAR_HALT,(void *)(uintptr_t)(index==0x81?in_ep:out_ep));
    } else {valid=0;}
    if(!valid) {checked(USB_RAW_IOCTL_EP0_STALL,NULL);return;}
    if(n>length) n=length;
    transfer(c.bRequestType&0x80?USB_RAW_IOCTL_EP0_WRITE:USB_RAW_IOCTL_EP0_READ,0,(void *)src,n);
}
int main(int argc,char **argv) {
    if(argc!=3) {fprintf(stderr,"usage: raw-bridge UDC_DRIVER UDC_DEVICE\n");return 2;}
    struct usb_raw_init init={.speed=USB_SPEED_FULL};
    if(strlen(argv[1])>=128 || strlen(argv[2])>=128) return 2;
    strcpy((char *)init.driver_name,argv[1]);strcpy((char *)init.device_name,argv[2]);
    fd=open("/dev/raw-gadget",O_RDWR);if(fd<0) fail("/dev/raw-gadget");
    checked(USB_RAW_IOCTL_INIT,&init);checked(USB_RAW_IOCTL_RUN,NULL);
    for(;;) {
        struct usb_raw_event *ev=calloc(1,sizeof(*ev)+256);if(!ev) fail("calloc");ev->length=256;
        checked(USB_RAW_IOCTL_EVENT_FETCH,ev);
        if(ev->type==USB_RAW_EVENT_CONTROL && ev->length==sizeof(struct usb_ctrlrequest)) {struct usb_ctrlrequest c;memcpy(&c,ev->data,sizeof(c));control(c);}
        /* Restart only after configuration: dwc2 may reset during initial enumeration. */
        if((ev->type==5 || ev->type==6) && configured) {fprintf(stderr,"USB reset/disconnect: rebinding\n");free(ev);return 0;}
        free(ev);
    }
}
