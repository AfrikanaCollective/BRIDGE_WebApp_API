import json
from django.core.management.base import BaseCommand
from api.models import PageImage

class Command(BaseCommand):
    help = 'Dumps a specific column from MyModel to a JSON file.'

    def add_arguments(self, parser):
        parser.add_argument('column_name', type=str, help='The name of the column to dump.')
        parser.add_argument('--output', type=str, default='output_data.json',
                            help='The output file path (default: output_data.json).')

    def handle(self, *args, **options):
        column_name = options['column_name']
        output_path = options['output']

        try:
            # Retrieve all values from the specified column
            column_data = list(PageImage.objects.values_list(column_name, flat=True))

            # Dump the data to a JSON file
            with open(output_path, 'w') as f:
                json.dump(column_data, f, indent=4)

            self.stdout.write(self.style.SUCCESS(
                f"Successfully dumped '{column_name}' data to {output_path}"
            ))
        except Exception as e:
            self.stderr.write(self.style.ERROR(f"Error dumping data: {e}"))
