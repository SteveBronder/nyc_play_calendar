from nyc_events_etl.cli import build_parser


def test_build_parser_parses_args():
    parser = build_parser()
    args = parser.parse_args(["in.pdf", "out.ics", "--dry-run"])
    assert args.pdf.name == "in.pdf"
    assert args.ics.name == "out.ics"
    assert args.dry_run is True
