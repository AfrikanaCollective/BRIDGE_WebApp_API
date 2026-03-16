import json
from django.core.serializers.json import DjangoJSONEncoder
from django.core.management.base import BaseCommand
from django.db import connection

class Command(BaseCommand):
    help = "Get file list of completed and reviewed uploads"

    def add_arguments(self, parser):
        parser.add_argument(
            '--output',
            default='pipeline_files.json',
            help='Output JSON file path'
        )

    def handle(self, *args, **options):
        output_file = options['output']

        # Example raw SQL query selecting multiple columns
        query = """
            SELECT 
                p.record_ipno,
                d.code AS document_type_code,
                t.status
            FROM api_documenttransaction t
            JOIN api_patientencounter p
                ON t.patient_id = p.id
            JOIN api_documenttype d
                ON t.document_type_id = d.id
            WHERE t.status = 'committed'
            ORDER BY p.record_ipno, d.code;
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