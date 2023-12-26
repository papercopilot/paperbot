
class Pipeline:
    """Pipeline for paperbot."""
    def __init__(self):
        print("Pipeline")
        
    def __call__(self):
        print("Pipeline")
    
if __name__ == "__main__":
    p = Pipeline()
    p.__call__( )