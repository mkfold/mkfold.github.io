#!/usr/bin/env python3

r"""
kfold.net blog generator
by mia k
"""

import hashlib
import json
import os
import shutil
import time
from argparse import ArgumentParser
from glob import glob
from os import path

import jinja2
import markdown


MD_EXTENSIONS = ["extra", "smarty", "meta"]

MANIFEST_PATH = "manifest.json"
CONTENT_PATH = "content"
TEMPLATE_PATH = "templates"
PUBLIC_PATH = "docs"

jenv = jinja2.Environment(loader=jinja2.FileSystemLoader(TEMPLATE_PATH))


def hash_file(fname):
    h = hashlib.sha256()
    with open(fname, "rb") as f:
        while True:
            b = f.read(h.block_size)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def gen_pages(docs, html_path, content_path):
    # dfmt = "%Y-%m-%d"
    tfmt = "%Y-%m-%d, %H:%M:%S"

    template = jenv.get_template("post.html")
    doc_props = {}
    for id_ in docs:
        fname = path.join(content_path, f"{id_}.md")

        curtime = time.strftime(tfmt)
        with open(fname, "r") as f:
            text = f.read()

        md = markdown.Markdown(extensions=MD_EXTENSIONS)
        body = md.convert(text)

        # get metadata using extension
        props = {k: "; ".join(v) for k, v in md.Meta.items()}
        props = {**props, "gen_time": curtime}

        fdir = path.join(html_path, id_)
        if not path.exists(fdir):
            os.mkdir(fdir)

        context = {"html": body, **props}

        if "date" in props:
            date_str = props.get("date")
            # ts = time.strptime(date_str, dfmt)
            # props["date"] = tuple(ts)
            context["date"] = date_str

        html = template.render({"doc": context})

        outpath = path.join(fdir, "index.html")
        with open(outpath, "w") as f:
            f.write(html)

        doc_props[id_] = props

    return doc_props


def del_pages(keys, html_path):
    for k in keys:
        if path.exists(p := path.join(html_path, k)):
            shutil.rmtree(p)
        else:
            print(f'warning: did not find directory "{p}" to delete')


def get_toc_data(id_, props):
    date_str = props["date"]
    o = {"id": id_, "title": props.get("title", id_), "date": date_str}
    if "desc" in props:
        o["desc"] = props["desc"]
    return o


def gen_toc(doc_props, html_path):
    template = jenv.get_template("toc.html")

    toc_data = [
        get_toc_data(id_, props)
        for id_, props in doc_props.items() if "date" in props
    ]
    toc_data = sorted(toc_data, key=lambda x: x["date"], reverse=True)
    context = {"toc": toc_data} if len(toc_data) != 0 else {}

    html = template.render(context)

    with open(path.join(html_path, "index.html"), "w") as f:
        f.write(html)


def make(manifest_path, markdown_path, html_path, rebuild=False):
    print("building site...")

    if not path.exists(html_path):
        os.mkdir(html_path)

    if path.exists(manifest_path):
        with open(manifest_path, "r") as f:
            try:
                manifest = json.load(f)
            except Exception as e:
                print(f"error: failed to load manifest; reason: {e.what()}\n")
                return
    else:
        print("no manifest found. creating empty manifest.")
        manifest = {}

    manifest_keys = set(manifest)

    def dirkey(x):
        return path.splitext(path.basename(x))[0]

    files = glob(path.join(markdown_path, "*.md"))
    found_keys = {dirkey(x) for x in files}
    print(f'found {len(files)} page(s) under "{markdown_path}".')

    new_keys = found_keys - manifest_keys
    del_keys = manifest_keys - found_keys

    print("computing file hashes...")
    file_hashes = {dirkey(f): hash_file(f) for f in files}
    manifest_hashes = {k: v["hash"] for k, v in manifest.items()}

    def stale(k, v):
        return k in file_hashes and v != file_hashes[k]

    def needs_update(k, v):
        return k not in del_keys and stale(k, v) or rebuild

    upd_keys = {k for k, v in manifest_hashes.items() if needs_update(k, v)}

    print(
        f"{len(new_keys)} new; "
        f"{len(upd_keys)} to update; "
        f"{len(del_keys)} to delete."
    )

    do_delete = len(del_keys) != 0
    do_update = len(new_keys) + len(upd_keys) != 0

    if do_delete:
        print(f"deleting {len(del_keys)} pages.")
        del_pages(del_keys, html_path)

    if do_update:
        print("generating pages...")
        gen_keys = new_keys | upd_keys - del_keys
        upd_props = gen_pages(gen_keys, html_path, markdown_path)
    else:
        upd_props = {}

    if do_delete or do_update:
        doc_props = {
            **{k: v for k, v in manifest.items() if k not in del_keys},
            **{k: {"hash": file_hashes[k], **v} for k, v in upd_props.items()},
        }
        toc_props = {k: v for k, v in doc_props.items() if "date" in v}
        print(f"generating table of contents for {len(toc_props)} articles...")
        gen_toc(toc_props, html_path)

        print("writing updated manifest.")
        with open(manifest_path, "w") as f:
            json.dump(doc_props, f)

    print("done.")


if __name__ == "__main__":
    p = ArgumentParser()
    p.add_argument("--markdown-path", type=str, default=CONTENT_PATH)
    p.add_argument("--html-path", type=str, default=PUBLIC_PATH)
    p.add_argument("--manifest-path", type=str, default=MANIFEST_PATH)

    p.add_argument("--rebuild", action="store_true")

    args = p.parse_args()

    make(args.manifest_path, args.markdown_path, args.html_path, args.rebuild)
