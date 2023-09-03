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


CONFIG_PATH = "config.json"
MANIFEST_PATH = "manifest.json"

CONTENT_PATH = "content"
TEMPLATE_PATH = "templates"
PUBLIC_PATH = "docs"

jenv = jinja2.Environment(loader=jinja2.FileSystemLoader(TEMPLATE_PATH))


if path.exists(CONFIG_PATH):
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        cfg = json.load(f)

        PUBLIC_PATH = cfg.get("PUBLIC_PATH", PUBLIC_PATH)
        TEMPLATE_PATH = cfg.get("TEMPLATE_PATH", TEMPLATE_PATH)
        CONTENT_PATH = cfg.get("CONTENT_PATH", CONTENT_PATH)


def get_args():
    p = ArgumentParser()
    p.add_argument("--markdown-path", type=str, default=CONTENT_PATH)
    p.add_argument("--html-path", type=str, default=PUBLIC_PATH)
    p.add_argument("--manifest-path", type=str, default=MANIFEST_PATH)

    p.add_argument("--rebuild", action="store_true")

    return p.parse_args()


def hash_file(fname):
    h = hashlib.sha256()
    with open(fname, "rb") as f:
        while True:
            b = f.read(h.block_size)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def iter_lines(text):
    i = prev = 0
    while i < len(text):
        while i < len(text) and text[i] != "\n":
            i += 1
        yield text[prev:i]
        i += 1
        prev = i


def gen_pages(docs, html_path):
    # dfmt = "%Y-%m-%d"
    tfmt = "%Y-%m-%d, %H:%M:%S"

    template = jenv.get_template("post.html")
    doc_props = {}
    for id_ in docs:
        fname = path.join(CONTENT_PATH, f"{id_}.md")

        curtime = time.strftime(tfmt)
        with open(fname, "r") as f:
            text = f.read()

        # extract properties in header
        props = {}
        skipline = 0
        for line in iter_lines(text):
            if not line.startswith("%"):
                break
            pk, pv = line.split(":", 1)
            pk, pv = pk[1:].strip(), pv.strip()
            props[pk] = pv
            skipline += 1

        props = {**props, "gen_time": curtime}

        for i, c in enumerate(text):
            if skipline == 0:
                break
            if c == "\n":
                skipline -= 1

        body = markdown.markdown(text[i:], extensions=["fenced_code"])

        fdir = path.join(html_path, id_)
        if not path.exists(fdir):
            os.mkdir(fdir)

        context = {"html": body, **props}

        if "date" in props:
            date_str = props.get("date")
            # props["date"] = time.strptime(date_str, dfmt)
            # context["date"] = time.strftime(dfmt, props["date"])
            context["date"] = date_str

        html = template.render({"doc": context})

        outpath = path.join(fdir, "index.html")
        with open(outpath, "w") as f:
            f.write(html)

        print("-", fdir)

        doc_props[id_] = props

    return doc_props


def del_pages(keys, html_path):
    for k in keys:
        if path.exists(p := path.join(html_path, k)):
            shutil.rmtree(p)
        else:
            print(f'warning: did not find directory "{p}" to delete')


def props_to_toc_data(id_, props):
    # tfmt = "%Y-%m-%d"
    # date_str = time.strftime(tfmt, time.struct_time(props["date"]))
    date_str = props["date"]
    o = {"id": id_, "title": props.get("title", id_), "date": date_str}
    if "desc" in props:
        o["desc"] = props["desc"]
    return o


def gen_toc(doc_props, html_path):
    template = jenv.get_template("toc.html")

    toc_data = [
        props_to_toc_data(id_, props)
        for id_, props in doc_props.items()
        if "date" in props
    ]
    toc_data = sorted(toc_data, key=lambda x: x["date"], reverse=True)
    context = {"toc": toc_data} if len(toc_data) != 0 else {}

    html = template.render(context)

    with open(path.join(html_path, "index.html"), "w") as f:
        f.write(html)


def main(manifest_path, markdown_path, html_path, rebuild=False):
    print("building site...")

    if not path.exists(html_path):
        os.mkdir(html_path)

    if path.exists(manifest_path):
        with open(manifest_path, "r") as f:
            try:
                manifest = json.load(f)
            except Exception as e:
                print(
                    f"error: failed to load manifest; reason: {e.what()}\n"
                    "starting with fresh manifest..."
                )
                manifest = {}
    else:
        print("no manifest found. creating empty manifest.")
        manifest = {}

    manifest_keys = set(manifest)

    def dirkey(x):
        return path.splitext(path.basename(x))[0]

    files = glob(path.join(markdown_path, "*.md"))
    # found_files = {dirkey(x): {"path": x} for x in files}
    found_keys = {dirkey(x) for x in files}

    print(f'found {len(files)} page(s) under "{markdown_path}".')

    new_keys = found_keys - manifest_keys
    del_keys = manifest_keys - found_keys

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
        upd_props = gen_pages(new_keys | upd_keys, html_path)
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
            json.dump(doc_props, f, indent=2)

    print("done.")


if __name__ == "__main__":
    args = get_args()
    main(args.manifest_path, args.markdown_path, args.html_path, args.rebuild)
