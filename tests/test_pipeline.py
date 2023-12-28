import paperbot

def test_pipeline():
    confs = ['iclr']
    years = [2024, 2023]
    years = [2023]
    p = paperbot.Pipeline(confs, years)
    assert p is not None
    p.launch()
    p.dump_summary()

if __name__ == "__main__":
    test_pipeline()