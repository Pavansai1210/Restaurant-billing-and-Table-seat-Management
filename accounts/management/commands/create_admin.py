from getpass import getpass

from django.core.management.base import BaseCommand, CommandError

from accounts.models import Staff


class Command(BaseCommand):
    help = 'Create the first restaurant admin. Runs only on the server.'

    def add_arguments(self, parser):
        parser.add_argument('username')

    def handle(self, *args, **options):
        username = options['username']
        if Staff.objects.filter(username=username).exists():
            raise CommandError('This username already exists.')

        password = getpass('Password: ')
        if password != getpass('Password again: '):
            raise CommandError('The passwords do not match.')
        if len(password) < 8:
            raise CommandError('The password must have at least 8 characters.')

        staff = Staff(username=username, role=Staff.Role.ADMIN)
        staff.set_password(password)
        staff.save()
        self.stdout.write(self.style.SUCCESS(f'Admin "{username}" created.'))