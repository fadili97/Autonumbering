def classFactory(iface):
    from .auto_numbering import AutoNumbering
    return AutoNumbering(iface)