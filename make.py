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
    "PageInfo",
    ("id_", "hash_", "gtime", "title", "desc", "date"),
    defaults=[None] * 2,
)

JINJA_TEMPLATE_PATH = "templates"
MD_EXTENSIONS = ["extra", "smarty", "meta"]

DEFAULT_MANIFEST_PATH = "manifest"
DEFAULT_CONTENT_PATH = "src"
DEFAULT_PUBLIC_PATH = "docs"

JENV = jinja2.Environment(loader=jinja2.FileSystemLoader(JINJA_TEMPLATE_PATH))
JENV.trim_blocks = True
JENV.lstrip_blocks = True
PAGE_TMPL = JENV.get_template("post.html")
TOFC_TMPL = JENV.get_template("tofc.html")

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


def process_md(text):
    md = markdown.Markdown(extensions=MD_EXTENSIONS)
    html = md.convert(text)

    def parse_meta_str(x):
        x = markdown.markdown(x)
        return x.removeprefix("<p>").removesuffix("</p>")

    meta = {k: [parse_meta_str(x) for x in v] for k, v in md.Meta.items()}
    meta = {k: v[0] if len(v) == 1 else v for k, v in meta.items()}
    return html, meta


def save_html(html, html_path):
    os.makedirs(html_path, exist_ok=True)
    dst_path = path.join(html_path, "index.html")
    with open(dst_path, "w") as f:
        f.write(html)


def copy_extra_files(md_path, html_path):
    srcs = [
        x for x in glob(path.join(md_path, "*"))
        if not x.endswith("index.md") and not path.isdir(x)
    ]
    dsts = [path.join(html_path, x.removeprefix(md_path)[1:]) for x in srcs]
    for src, dst in zip(srcs, dsts):
        shutil.copyfile(src, dst)


def make_tofc(page_infos, site_info, html_path):
    tofc_infos = [x for x in page_infos if x.date is not None]
    tofc = sorted(tofc_infos, key=lambda x: x.date, reverse=True)
    html = TOFC_TMPL.render(
        {"site": {**site_info, "gtime": time.strftime(TIME_FMT)}, "tofc": tofc}
    )
    save_html(html, html_path)
    return len(tofc_infos)


def make_pages(docs, site_info, html_path):
    fields = PageInfo._fields[2:]  # data expected from page generation output
    new_props = {}
    for id_, fname, hash_ in docs:
        with open(fname, "rb") as f:
            if (h := hash_file(f)) == hash_:
                continue
            text = f.read().decode("utf-8")

        gtime = time.strftime(TIME_FMT)
        html, meta = process_md(text)
        meta = {"title": id_, **meta, "gtime": gtime}

        doc = {**meta, "html": html}
        html = PAGE_TMPL.render({"site": site_info, "doc": doc})
        save_html(html, path.join(html_path, id_))

        meta = {k: v for k, v in meta.items() if k in fields}
        new_props[id_] = PageInfo(id_, h, **meta)

    return new_props


def del_pages(ids, html_path):
    for i in ids:
        if path.exists(p := path.join(html_path, i)):
            shutil.rmtree(p)
        else:
            print(f'warning: did not find directory "{p}" to delete')


def load_root_md(info_md_path):
    with open(info_md_path, "rb") as f:
        hash_ = hash_file(f)
        info_md = f.read().decode("utf-8")
    html, site_meta = process_md(info_md)
    site_meta["html"] = html
    return site_meta, hash_


def save_manifest(f, info_digest, page_infos):
    csv.writer(f).writerows([info_digest] + page_infos)


def load_manifest(manifest_path):
    with open(manifest_path, "r", newline="") as f:
        info_digest = tuple(f.readline().strip().rsplit(",", 2))
        post_infos = [PageInfo(*v) for v in csv.reader(f)]
    return info_digest, post_infos


def make(manifest_path, md_path, html_path, copy_extras=False, force=False):
    manifest_path = path.normpath(manifest_path)
    md_path = path.normpath(md_path)
    html_path = path.normpath(html_path)

    def path2id(x):
        return path.basename(path.dirname(x))

    def id2path(x):
        return path.join(md_path, x, "index.md")

    assert path.exists(info_md_path := path.join(md_path, "index.md")), \
        "error: root index.md file not found"

    site_info, info_hash = load_root_md(info_md_path)

    manif = {}
    info_updated = False
    if not force and path.exists(manifest_path):
        manif_header, manif_infos = load_manifest(manifest_path)
        manif |= {x.id_: x for x in manif_infos}
        print(f"loaded manifest with {len(manif)} post(s)")

        _, prev_info_hash = manif_header
        if (info_updated := prev_info_hash != info_hash):
            print("warning: global site info changed. forcing full rebuild.")
            force = True
    else:
        print(
            "warning: no manifest found or full rebuild forced; "
            "starting with empty manifest."
        )

    md_files = glob(path.join(md_path, "*", "index.md"))
    html_files = glob(path.join(html_path, "*", "index.html"))

    mf_ids = set(manif)
    md_ids = {path2id(x) for x in md_files}
    html_ids = {path2id(x) for x in html_files}

    matched_i = mf_ids & html_ids  # matched: has mf entry and html
    del_i = mf_ids - md_ids        # deleted: any mf entry not in md dir
    new_i = md_ids if force else md_ids - matched_i  # new: any "unmatched" md
    upd_i = set() if force else md_ids & matched_i   # updated: any md w/ match

    if len(missing := mf_ids - html_ids):
        print(f"warning: {len(missing)} page(s) in manifest with no html")

    os.makedirs(html_path, exist_ok=True)

    new_data = (
        make_pages(x, site_info, html_path)
        if len(x := [(k, id2path(k), None) for k in new_i]) else {}
    )
    print(f":: {len(new_data)} new page(s) generated")

    upd_data = (
        make_pages(x, site_info, html_path)
        if len(x := [(k, id2path(k), manif[k].hash_) for k in upd_i]) else {}
    )
    print(f":: {len(upd_data)} page(s) updated")

    if len(to_delete := del_i & html_ids):
        del_pages(to_delete, html_path)
        print(f":: {len(to_delete)} page(s) deleted from disk")

    upd_data |= new_data
    if force or info_updated or len(del_i) or len(upd_data):
        manif = {k: x for k, x in manif.items() if k not in del_i}
        manif |= upd_data

        if len(del_i):
            print(f":: {len(del_i)} page(s) dropped from manifest")

        page_infos = list(manif.values())
        n_articles = make_tofc(page_infos, site_info, html_path)
        print(f":: index with {n_articles} post(s) generated")

        manif_header = (site_info["title"], info_hash)
        with open(manifest_path, "w", newline="") as f:
            save_manifest(f, manif_header, page_infos)
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
