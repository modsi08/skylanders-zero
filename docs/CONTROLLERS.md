# Optional controller backend

The web UI offers Portal, Idle and a controller integration mode. No controller
backend is supplied, and 8BitDo Pro 2 translation, PS button and rumble are not
implemented or claimed as supported. Controller mode is disabled unless an
administrator configures a foreground backend command.

Example interface only (not an executable supplied by this project):

```ini
SKYLANDERS_CONTROLLER_COMMAND='["/absolute/path/to/adapter", "--foreground"]'
```

Put that setting in /etc/skylanders-zero.env. A compatible backend must claim and
release its own gadget, remain in the foreground and clean up bindings on SIGTERM.
Do not also enable a standalone service for that backend. Only one backend may own
the UDC. Mode choices survive reboot. Idle releases the app's USB binding but does
not unload dwc2. A running controller process is not evidence of pairing or PS3
recognition. RosettaPad is a separate project; its controller support should be
checked before trying to integrate it: https://github.com/ihasTaco/RosettaPad
