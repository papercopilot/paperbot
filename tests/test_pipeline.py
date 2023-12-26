import paperbot

def test_pipeline():
    p = paperbot.Pipeline(conf='iclr', year=2024)
    assert p is not None

if __name__ == "__main__":
    test_pipeline()