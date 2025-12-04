import json
from django.core.serializers.json import DjangoJSONEncoder
from django.core.management.base import BaseCommand
from django.db import connection

class Command(BaseCommand):
    help = "Dump transaction time data from PostgreSQL query into a JSON file."

    def add_arguments(self, parser):
        parser.add_argument(
            '--output',
            default='transaction_time.json',
            help='Output JSON file path'
        )

    def handle(self, *args, **options):
        output_file = options['output']

        # Example raw SQL query selecting multiple columns
        query = """
            SELECT 
              d.code,
              EXTRACT(EPOCH FROM (t.updated_at - t.created_at)) AS duration_seconds
            FROM api_documenttransaction t
            JOIN api_documenttype d
              ON t.document_type_id = d.id
            WHERE t.updated_at IS NOT NULL 
              AND t.created_at IS NOT NULL
              AND t.status = 'committed';
        """

        with connection.cursor() as cursor:
            cursor.execute(query)
            columns = [col[0] for col in cursor.description]
            rows = cursor.fetchall()

        # Convert rows to list of dicts
        data = [
            dict(zip(columns, row))
            for row in rows
        ]

        # Save JSON
        with open(output_file, 'w') as f:
            json.dump(data, f, cls=DjangoJSONEncoder, indent=2)

        self.stdout.write(self.style.SUCCESS(f"Saved {len(data)} records to {output_file}"))
