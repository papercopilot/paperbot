import paperbot

def test_pipeline():
    p = paperbot.Pipeline(conf='iclr', year=2024)
    assert p is not None
    p.launch()

if __name__ == "__main__":
    test_pipeline()