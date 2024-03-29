#!/usr/bin/env python3

r"""
kfold.net blog generator
by mia k
"""

import hashlib
import csv
import os
import shutil
import time
from collections import namedtuple
from glob import glob
from os import path

import jinja2
import markdown

PageInfo = namedtuple(
    "PageInfo", ("id_", "hash_", "gtime", "title", "desc", "date")
)

JINJA_TEMPLATE_PATH = "templates"
MD_EXTENSIONS = ["extra", "smarty", "meta"]

DEFAULT_MANIFEST_PATH = "manifest"
DEFAULT_CONTENT_PATH = "src"
DEFAULT_PUBLIC_PATH = "docs"

JENV = jinja2.Environment(loader=jinja2.FileSystemLoader(JINJA_TEMPLATE_PATH))
JENV.trim_blocks = True
JENV.lstrip_blocks = True
PAGE_TEMPLATE = JENV.get_template("post.html")
TOFC_TEMPLATE = JENV.get_template("toc.html")

DATE_FMT = "%Y-%m-%d"
TIME_FMT = DATE_FMT + "T%H:%M:%S"


def hash_file(f):
    h = hashlib.sha256()
    while True:
        b = f.read(h.block_size)
        if not b:
            break
        h.update(b)
    f.seek(0)
    return h.hexdigest()


def generate_page(text):
    gtime = time.strftime(TIME_FMT)

    md = markdown.Markdown(extensions=MD_EXTENSIONS)
    body = md.convert(text)

    props = {k: "; ".join(v).strip() for k, v in md.Meta.items()}
    props = {"date": None, "gtime": gtime, **props}

    ctx = {"doc": {**props, "html": body}}
    html = PAGE_TEMPLATE.render(ctx)

    return html, props


def generate_toc(page_info):
    toc = sorted(page_info, key=lambda x: x.date, reverse=True)
    return TOFC_TEMPLATE.render({"toc": toc} if len(toc) else {})


def save_html(html, html_path):
    os.makedirs(html_path, exist_ok=True)
    dst_path = path.join(html_path, "index.html")
    with open(dst_path, "w") as f:
        f.write(html)


def copy_extra_files(md_path, html_path):
    src_paths = [
        x for x in glob(path.join(md_path, "*"))
        if not x.endswith("index.md") and not path.isdir(x)
    ]
    dst_paths = [
        path.join(html_path, x.removeprefix(md_path)[1:]) for x in src_paths
    ]
    for src, dst in zip(src_paths, dst_paths):
        shutil.copyfile(src, dst)


def make_pages(docs, html_path, force_update=False):
    new_props = {}
    for id_, fname, hash_ in docs:
        with open(fname, "rb") as f:
            h = hash_file(f)
            if not force_update and h == hash_:
                continue
            text = f.read().decode("utf-8")

        html, props = generate_page(text)
        new_props[id_] = PageInfo(id_, h, **props)

        dst_path = path.join(html_path, id_)
        save_html(html, dst_path)
    return new_props


def del_pages(ids, html_path):
    for i in ids:
        if path.exists(p := path.join(html_path, i)):
            shutil.rmtree(p)
        else:
            print(f'warning: did not find directory "{p}" to delete')


def save_manifest(f, manifest):
    csv.writer(f).writerows(manifest)


def load_manifest(f):
    return [PageInfo(*v) for v in csv.reader(f)]


def make(manifest_path, md_path, html_path, copy_extras=False, force=False):
    manifest_path = path.normpath(manifest_path)
    md_path = path.normpath(md_path)
    html_path = path.normpath(html_path)

    def path2id(x):
        return path.basename(path.dirname(x))

    def id2path(x):
        return path.join(md_path, x, "index.md")

    if path.exists(manifest_path):
        with open(manifest_path, "r", newline="") as f:
            manif = {x.id_: x for x in load_manifest(f)}
        print(f"loaded manifest with {len(manif)} post(s)")
    else:
        print("warning: no manifest found. creating empty manifest")
        manif = {}

    md_files = glob(path.join(md_path, "*", "index.md"))
    html_files = glob(path.join(html_path, "*", "index.html"))

    mf_ids = set(manif)
    md_ids = {path2id(x) for x in md_files}
    html_ids = {path2id(x) for x in html_files}

    matched_i = mf_ids & html_ids  # matched: has mf entry and html
    del_i = mf_ids - md_ids        # deleted: any mf entry not in md dir
    new_i = md_ids - matched_i     # new: any in md dir not in "matched"
    upd_i = md_ids & matched_i     # updated: any in md dir with match

    if len(missing := mf_ids - html_ids):
        print(f"warning: {len(missing)} page(s) in manifest with no html")

    os.makedirs(html_path, exist_ok=True)

    new_data = (
        make_pages(x, html_path)
        if len(x := [(k, id2path(k), None) for k in new_i]) else {}
    )
    print(f":: {len(new_data)} new page(s) generated")

    upd_data = (
        make_pages(x, html_path, force)
        if len(x := [(k, id2path(k), manif[k].hash_) for k in upd_i]) else {}
    )
    print(f":: {len(upd_data)} page(s) updated")

    if len(to_delete := del_i & html_ids):
        del_pages(to_delete, html_path)
    print(f":: {len(to_delete)} page(s) deleted from disk")

    upd_data |= new_data
    if force or len(del_i) or len(upd_data):
        manif = {k: x for k, x in manif.items() if k not in del_i}
        manif |= upd_data
        toc_data = [x for x in manif.values() if x.date is not None]

        if len(del_i):
            print(f":: {len(del_i)} page(s) dropped from manifest")

        toc_html = generate_toc(toc_data)
        save_html(toc_html, html_path)
        print(f":: index with {len(toc_data)} post(s) generated")

        with open(manifest_path, "w", newline="") as f:
            save_manifest(f, manif.values())
        print(":: updated manifest")

    if copy_extras:
        copy_extra_files(md_path, html_path)
        for i in upd_data:
            copy_extra_files(path.dirname(id2path(i)), path.join(html_path, i))

    print("done")


if __name__ == "__main__":
    from argparse import ArgumentParser
    p = ArgumentParser()
    p.add_argument("--manifest-path", type=str, default=DEFAULT_MANIFEST_PATH)
    p.add_argument("--md-path", type=str, default=DEFAULT_CONTENT_PATH)
    p.add_argument("--html-path", type=str, default=DEFAULT_PUBLIC_PATH)
    p.add_argument("--copy-extras", "-c", action="store_true")
    p.add_argument("--force", "-f", action="store_true")

    make(**vars(p.parse_args()))
