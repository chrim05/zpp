class Instruction:
  def __init__(self, kind, **kwargs):
    self.__dict__ = kwargs
    self.kind = kind

class Builder:
  def __init__(self, block):
    self.block = block

  def load(self, resulting_type, ):
    self.load()
