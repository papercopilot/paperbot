import paperbot

def test_pipeline():
    confs = ['iclr', 'nips', 'icml', 'corl', 'emnlp']
    years = range(2024, 2012, -1)
    # confs = ['iclr']
    # years = [2020]
    p = paperbot.Pipeline(confs, years)
    assert p is not None
    p.launch()
    p.dump_summary()
    p.dump_keywords()

if __name__ == "__main__":
    test_pipeline()