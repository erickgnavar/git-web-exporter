#!/usr/bin/env python
import difflib
import shutil
import sys
from pathlib import Path

from git import Repo
from jinja2 import Template
from markdown import markdown
from slugify import slugify


def extract_repo_data(repo_path: Path) -> dict:
    """
    Read repo's commits and extract all the relevant data to produce a website
    """
    repo = Repo(repo_path)

    # this is the result of executing:
    # printf '' | git hash-object -t tree --stdin
    # this is the origin hash that can be used to compare any commit, it's
    # equivalent to --root
    rev = "4b825dc642cb6eb9a060e54bf8d69288fbee4904"
    data = []

    # FIXME: find another way to start from the beginning without loading
    # all the commits in memory
    commits = reversed(list(repo.iter_commits()))

    for commit in commits:
        title, _, *body = commit.message.split("\n")
        sys.stdout.write(f'Processing "{title}"...\n')

        changes = []

        for diff in commit.diff(rev):
            a_blob = diff.a_blob
            b_blob = diff.b_blob

            # only process plain text changes, for now we're not processing binary content
            if a_blob is not None and not a_blob.mime_type.startswith("text"):
                continue

            if b_blob is not None and not b_blob.mime_type.startswith("text"):
                continue

            original = []
            modified = []
            blob_path = None

            if a_blob is None and b_blob is not None:
                # there is a new file
                original = []
                modified = b_blob.data_stream.read().decode("utf8").split("\n")
                blob_path = b_blob.path

            elif a_blob is not None and b_blob is None:
                # a file was deleted
                original = a_blob.data_stream.read().decode("utf8").split("\n")
                modified = []
                blob_path = a_blob.path

            else:
                # there are changes in a existing file
                original = a_blob.data_stream.read().decode("utf8").split("\n")
                modified = b_blob.data_stream.read().decode("utf8").split("\n")

                # both have the same path so we can use any of them
                blob_path = a_blob.path

            delta = difflib.unified_diff(modified, original, blob_path, blob_path)

            changes.append({"path": blob_path, "diff": "\n".join(delta)})

        data.append(
            {
                "title": title,
                "hash": commit.hexsha,
                "body": "\n".join(body),
                "changes": changes,
            }
        )

        rev = commit

    return data


def render_repo_data(data: dict) -> None:
    """
    Render received data into html files
    """

    base_html = Path("./templates/base.html")
    styles = Path("./templates/styles.css")

    with open(base_html) as f:
        template = Template(f.read())

    output_dir = Path("./output")

    if not output_dir.exists():
        output_dir.mkdir()

    shutil.copy(styles, output_dir / Path("styles.css"))

    generate_index = True

    toc = []
    for page in data:
        title = page["title"]
        path = slugify(title) + ".html"
        toc.append({"title": title, "path": f"./{path}"})

    for page in data:
        title = page["title"]
        html_filename = Path(slugify(title) + ".html")

        changes = []

        for change in page["changes"]:
            diff = change["diff"]

            changes.append(
                {
                    "path": change["path"],
                    "diff": render_markdown(f"``` diff\n{diff}\n```"),
                }
            )

        context = {
            "title": page["title"],
            "hash": page["hash"],
            "body": render_markdown(page["body"]),
            "toc": toc,
            "changes": changes,
        }

        with open(output_dir / html_filename, "w") as f:
            f.write(template.render(**context))

        # generate a index.html using first commit page
        if generate_index:
            with open(output_dir / Path("index.html"), "w") as f:
                f.write(template.render(**context))
            generate_index = False

    return None


def render_markdown(md_content: str) -> str:
    """
    Render the given markdown content using extension for code blocks

    fenced_code make code blocks render properly
    codehilite add syntax highlighting to code blocks
    """
    return markdown(md_content, extensions=["codehilite", "fenced_code"])


def main():
    if len(sys.argv) < 2:
        sys.stdout.write("Please provider a repo\n")
        exit(1)

    _, repo, *rest = sys.argv

    repo_path = Path(repo)

    if not repo_path.exists():
        sys.stderr.write(f"{repo_path} doesn't exist")
        exit(1)

    data = extract_repo_data(repo_path)
    render_repo_data(data)


if __name__ == "__main__":
    main()
