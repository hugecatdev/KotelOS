# файловые операции: cp/mv/rm из busybox (рекурсия, ссылки, права), корзина по freedesktop.org Trash
import os
import time

from . import TRASH, basename, dirname, exists, join, mkdirs, q, read, sh, write


def free_name(folder, name):
    """name, а если занято - «name (2)», «name (3)»... с сохранением расширения."""
    if not exists(join(folder, name)):
        return name
    stem, ext = name, ""
    i = name.rfind(".")
    if i > 0:
        stem, ext = name[:i], name[i:]
    n = 2
    while exists(join(folder, "%s (%d)%s" % (stem, n, ext))):
        n += 1
    return "%s (%d)%s" % (stem, n, ext)


def paste(paths, folder, move=False):
    """Скопировать или перенести пути в папку; ошибки - списком строк."""
    errs = []
    for p in paths:
        if move and dirname(p) == folder.rstrip("/"):
            continue
        if folder == p or folder.startswith(p.rstrip("/") + "/"):
            errs.append("%s: нельзя положить папку в саму себя" % basename(p))
            continue
        dst = join(folder, free_name(folder, basename(p)))
        if not sh("%s %s %s 2>/dev/null" % ("mv" if move else "cp -a", q(p), q(dst))):
            errs.append("%s: не получилось" % basename(p))
    return errs


def rename(path, name):
    if not name or "/" in name:
        return "имя без «/»"
    dst = join(dirname(path), name)
    if exists(dst):
        return "«%s» уже есть" % name
    try:
        os.rename(path, dst)
    except OSError as e:
        return str(e)
    return None


def new_folder(folder, name):
    try:
        os.mkdir(join(folder, free_name(folder, name)))
    except OSError as e:
        return str(e)
    return None


def new_file(folder, name):
    p = join(folder, free_name(folder, name))
    try:
        open(p, "w").close()
    except OSError as e:
        return str(e)
    return None


def remove(paths):
    errs = []
    for p in paths:
        if not sh("rm -rf %s 2>/dev/null" % q(p)):
            errs.append(basename(p))
    return errs


# корзина: files/<имя> и info/<имя>.trashinfo с исходным путём и временем удаления


def in_trash(path):
    return path.startswith(TRASH + "/files/") or path.rstrip("/") == TRASH + "/files"


def trash(paths):
    files, info = TRASH + "/files", TRASH + "/info"
    mkdirs(files)
    mkdirs(info)
    errs = []
    for p in paths:
        name = free_name(files, basename(p))
        while exists(join(info, name + ".trashinfo")):
            name = free_name(files, name + "_")
        y, mo, d, h, mi, s = time.localtime()[:6]
        write(join(info, name + ".trashinfo"),
              "[Trash Info]\nPath=%s\nDeletionDate=%04d-%02d-%02dT%02d:%02d:%02d\n" % (p, y, mo, d, h, mi, s))
        if not sh("mv %s %s 2>/dev/null" % (q(p), q(join(files, name)))):
            os.remove(join(info, name + ".trashinfo"))
            errs.append(basename(p))
    return errs


def origin(path):
    """Откуда удалён файл корзины."""
    for line in read(TRASH + "/info/" + basename(path) + ".trashinfo").split("\n"):
        if line.startswith("Path="):
            return line[5:]
    return None


def restore(paths):
    errs = []
    for p in paths:
        o = origin(p)
        if not o:
            errs.append("%s: неизвестно, откуда" % basename(p))
            continue
        mkdirs(dirname(o))
        dst = join(dirname(o), free_name(dirname(o), basename(o)))
        if sh("mv %s %s 2>/dev/null" % (q(p), q(dst))):
            try:
                os.remove(TRASH + "/info/" + basename(p) + ".trashinfo")
            except OSError:
                pass
        else:
            errs.append(basename(p))
    return errs


def purge(paths):
    """Удалить из корзины насовсем."""
    errs = remove(paths)
    for p in paths:
        try:
            os.remove(TRASH + "/info/" + basename(p) + ".trashinfo")
        except OSError:
            pass
    return errs


def empty_trash():
    sh("rm -rf %s %s" % (q(TRASH + "/files"), q(TRASH + "/info")))
