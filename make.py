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
from argparse import ArgumentParser
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

DEFAULT_MANIFEST_PATH = "manifest.json"
DEFAULT_CONTENT_PATH = "content"
DEFAULT_PUBLIC_PATH = "docs"

JENV = jinja2.Environment(loader=jinja2.FileSystemLoader(JINJA_TEMPLATE_PATH))
JENV.trim_blocks = True
JENV.lstrip_blocks = True
PAGE_TEMPLATE = JENV.get_template("post.html")
TOFC_TEMPLATE = JENV.get_template("toc.html")

DATE_FMT = "%Y-%m-%d"
TIME_FMT = "%Y-%m-%dT%H:%M:%S"


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
    props = {**props, "gtime": gtime}

    ctx = {"doc": {**props, "html": body}}
    html = PAGE_TEMPLATE.render(ctx)

    return html, props


def generate_toc(page_info):
    toc = sorted(page_info, key=lambda x: x.date, reverse=True)
    return TOFC_TEMPLATE.render({"toc": toc} if len(toc) else {})


def save_page(html, html_path, id_=None):
    fdir = path.join(html_path, id_) if id_ is not None else html_path
    outpath = path.join(fdir, "index.html")

    os.makedirs(fdir, exist_ok=True)
    with open(outpath, "w") as f:
        f.writelines(x.strip() + "\n" for x in html.split("\n"))


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
        save_page(html, html_path, id_=id_)

    return new_props


def del_pages(keys, html_path):
    for k in keys:
        if path.exists(p := path.join(html_path, k)):
            shutil.rmtree(p)
        else:
            print(f'warning: did not find directory "{p}" to delete')


def save_manifest(f, manifest):
    csv.writer(f).writerows(manifest)


def load_manifest(f):
    return [PageInfo(*v) for v in csv.reader(f)]


def make(manifest_path, markdown_path, html_path, rebuild=False, v=False):
    vprint = print if v else bool  # hehe

    def pathkey(x):
        return path.splitext(path.basename(x))[0]

    def keypath(x):
        return path.join(markdown_path, f"{x}.md")

    if path.exists(manifest_path):
        with open(manifest_path, "r", newline="") as f:
            manifest = {x.id_: x for x in load_manifest(f)}
        vprint(f'{len(manifest)} item(s) in manifest at "{manifest_path}"')
    else:
        print("no manifest found. creating empty manifest.")
        manifest = {}

    md_files = glob(path.join(markdown_path, "*.md"))
    html_files = glob(path.join(html_path, "*", "index.html"))

    mf_keys = set(manifest)
    md_keys = {pathkey(x) for x in md_files}
    html_keys = {pathkey(path.split(x)[0]) for x in html_files}

    vprint(
        f'{len(md_keys)} md files(s) under "{markdown_path}".\n'
        f'{len(html_keys)} html files(s) under "{html_path}".'
    )

    matched_k = mf_keys & html_keys  # matched: has mf entry and html
    del_k = mf_keys - md_keys        # deleted: any mf entry not in md dir
    new_k = md_keys - matched_k      # new: any in md dir not in "matched"
    upd_k = md_keys & matched_k      # updated: any in md dir with match

    if len(missing := (mf_keys - html_keys)):
        print(f"warning: {len(missing)} page(s) in manifest with no HTML.")

    do_delete = len(del_k) != 0
    if do_delete:
        deleted = del_k & html_keys
        print(
            f"deleting {len(deleted)} page(s); "
            f"dropping {len(del_k - html_keys)} item(s) from manifest."
        )
        del_pages(deleted, html_path)

    os.makedirs(html_path, exist_ok=True)

    upd_data = {}
    if len(new_k):
        print(f"found {len(new_k)} new pages; generating...")
        new = [(k, keypath(k), None) for k in new_k]
        upd_data |= make_pages(new, html_path)

    if len(upd_k):
        print(f"{len(upd_k)} existing page(s); checking for updates...")
        updates = [(k, keypath(k), manifest[k].hash_) for k in upd_k]
        upd_data |= make_pages(updates, html_path, force_update=rebuild)

    if do_delete or len(upd_data):
        manifest = {
            **{k: v for k, v in manifest.items() if k not in del_k},
            **{k: v for k, v in upd_data.items()},
        }
        toc_data = [x for x in manifest.values() if x.date is not None]

        print(f"generating table of contents for {len(toc_data)} articles...")
        toc_html = generate_toc(toc_data)
        save_page(toc_html, html_path)

        print("writing updated manifest.")
        with open(manifest_path, "w", newline="") as f:
            save_manifest(f, manifest.values())

    print("done.")


if __name__ == "__main__":
    p = ArgumentParser()
    p.add_argument("--manifest-path", type=str, default=DEFAULT_MANIFEST_PATH)
    p.add_argument("--markdown-path", type=str, default=DEFAULT_CONTENT_PATH)
    p.add_argument("--html-path", type=str, default=DEFAULT_PUBLIC_PATH)
    p.add_argument("--rebuild", action="store_true")
    p.add_argument("-v", action="store_true")

    make(**vars(p.parse_args()))
