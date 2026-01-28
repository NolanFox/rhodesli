from fasthtml.common import *

app, rt = fast_app()


@rt("/")
def get():
    return Titled("Rhodesli", P("Welcome to Rhodesli - Family Lineage Tool"))


serve()
