import pathlib

import feedparser
import pytest
import sqlite_utils
from click.testing import CliRunner

from feed_to_sqlite import ingest_feed
from feed_to_sqlite.cli import cli
from feed_to_sqlite.ingest import FEEDS_TABLE, extract_entry_fields


def feed(name):
    with (pathlib.Path(__file__).parent / name).open() as f:
        return f.read()


@pytest.fixture
def newsblur():
    return feed("newsblur.xml")


@pytest.fixture
def instapaper():
    return feed("instapaper.xml")


@pytest.fixture
def db():
    return sqlite_utils.Database(memory=True)


def test_version():
    runner = CliRunner()
    with runner.isolated_filesystem():
        result = runner.invoke(cli, ["--version"])
        assert 0 == result.exit_code
        assert result.output.startswith("cli, version ")


def test_load_feed(db, newsblur):
    "check basic functionality"
    ingest_feed(db, feed_content=newsblur)

    assert "chrisamicos_blurblog" in db.table_names()

    table = db["chrisamicos_blurblog"]

    assert table.count == 25


def test_feeds_table(db, newsblur, instapaper):
    "check that a feeds table is created"
    ingest_feed(db, feed_content=newsblur)
    ingest_feed(db, feed_content=instapaper)

    # one table per feed, plus feeds
    assert len(db.tables) == 3
    assert FEEDS_TABLE in db.table_names()
    assert db[FEEDS_TABLE].count == 2


def test_shared_table(db, newsblur, instapaper):
    table_name = "links"
    ingest_feed(db, feed_content=newsblur, table_name=table_name)
    ingest_feed(db, feed_content=instapaper, table_name=table_name)

    # links and feeds
    assert len(db.tables) == 2
    assert FEEDS_TABLE in db.table_names()
    assert table_name in db.table_names()

    assert db[table_name].count == 35


def test_transform_feed(db, instapaper):
    def capitalize(table, entry, feed_details, client=None):
        row = extract_entry_fields(table, entry, feed_details)
        row["title"] = row["title"].upper()
        return row

    ingest_feed(db, feed_content=instapaper, table_name="links", normalize=capitalize)
    feed = feedparser.parse(instapaper)

    for entry in feed.entries:
        row = db["links"].get(entry.id)
        assert row["title"] == entry["title"].upper()


def test_alter_table(db, instapaper):
    def add_test_column(table, entry, feed_details, client=None):
        row = extract_entry_fields(table, entry, feed_details)
        row["extra"] = True  # this will add a column
        return row

    ingest_feed(
        db,
        feed_content=instapaper,
        table_name="links",
        normalize=add_test_column,
        alter=True,
    )

    columns = db["links"].columns_dict

    assert "extra" in columns
    assert columns["extra"] == int
