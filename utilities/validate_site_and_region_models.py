import os
import json
import pathlib
import jsonschema
import json.decoder
from argparse import ArgumentError, ArgumentParser, ArgumentTypeError

# takes a directory of site and/or region models and runs format validation on all of them

def simple_validate(schemaName, model_file):
    schema_file = pathlib.Path(schemaName).resolve()
    with schema_file.open() as fo:
        schema = json.load(fo)

    model = os.path.split(model_file)[-1]
    model_file = pathlib.Path(model_file).resolve()
    with model_file.open() as fo:
        instance = json.load(fo)

    try:
        jsonschema.validate(instance=instance, schema=schema)
        print(f"{model} passed\n")
    except jsonschema.ValidationError as e:
        print(f"{model} is invalid (path: {model_file})")
        print(f"Location of error is {e.json_path}\n")
        #print(f"Error is {e.message}") # uncomment for more detail


def main():
    parser = ArgumentParser()
    parser.add_argument('-p', '--path', type=str, dest='path', help='Path to folder containing site and/or region models')
    parser.add_argument('-s', '--schema_file', type=str, dest='schemaName', required=False, default='smart.schema.json', help='Path to schema.json file')
    try: 
         parsed = parser.parse_args()
    except ArgumentError as error: 
        raise error

    modelFiles = sorted(os.listdir(parsed.path))
    modelFiles = [os.path.join(parsed.path, file) for file in modelFiles if os.path.splitext(file)[-1] == '.geojson']

    for model in modelFiles:
        simple_validate(parsed.schemaName, model)

if __name__ == "__main__":
    main()
