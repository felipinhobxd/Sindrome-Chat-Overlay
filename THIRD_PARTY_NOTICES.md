# Third-party notices

This project was independently written in Python and does not incorporate source code from the projects used as visual and behavioral references. General ideas such as a transparent, resizable, always-on-top window and click-through mode were studied in:

- [Transparent Twitch Chat Overlay](https://github.com/baffler/Transparent-Twitch-Chat-Overlay), GPL-3.0.
- [Ghost Chat](https://github.com/Enubia/ghost-chat), DBAD Public License 1.2.

Dependencies installed during the build include:

- [PySide6 / Qt for Python](https://doc.qt.io/qtforpython-6/licenses.html), available under LGPL-3.0/GPL-3.0 and commercial licensing options, depending on the components used.
- [Requests](https://github.com/psf/requests), Apache-2.0.
- [gRPC Python](https://github.com/grpc/grpc), Apache-2.0.
- [Protocol Buffers](https://github.com/protocolbuffers/protobuf), BSD-3-Clause.
- The minimal YouTube `streamList` protocol schema used by the client is derived from Google's published API schema, Apache-2.0.
- [PyInstaller](https://pyinstaller.org/), GPL-2.0 with the bootloader distribution exception.
- [Pillow](https://python-pillow.github.io/), historical HPND license.
- [Inno Setup](https://jrsoftware.org/isinfo.php), used only to compile the Windows installer and distributed under its own license.

When redistributing a build, retain this file, the application's `LICENSE`, and any notices or licenses added by its dependencies. Consult the links above for the complete terms that apply to the versions installed at build time.
