import paperbot

def test_pipeline():
    confs = ['iclr', 'nips', 'icml', 'corl', 'emnlp']
    # confs = ['emnlp']
    years = range(2024, 2012, -1)
    # years = [2020]
    p = paperbot.Pipeline(confs, years)
    assert p is not None
    p.launch()
    p.dump_summary()

if __name__ == "__main__":
    test_pipeline()