import traceback

from django.core.management.base import BaseCommand
from catalogue.models import Record

class Command(BaseCommand):
    help = 'Formalize table data based on predefined pattern'

    def add_arguments(self,parser):
        parser.add_argument('type', type=str,help="The type of the data to formalize, possible values are 'stylelinks'")
        parser.add_argument(
            '--id',
            action='store',
            dest='id',
            help='The data id',
        )

    def handle(self, *args, **options):

        #regenerate style links
        if options["type"] == "stylelinks":
            changedRecords = 0
            records = Record.objects.all()
            if options["id"]:
                records = records.filter(id=options["id"])
            for record in records:
                try:
                    if record.refresh_style_links():
                        print("Fix the style links for the layer {1}({0}).".format(record.id,record.identifier))
                        changedRecords += 1
                except:
                    print("Formalize style data failed for record {1}({0})".format(record.id,record.identifier))
                    traceback.print_exc()

            print("{} records have been changed.".format(changedRecords))

