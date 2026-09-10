import json
from decimal import Decimal, InvalidOperation
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from icpd.models import Activity, ActivityIndicator, Commitment, IndicatorYearData, Objective


KES_PER_MILLION = Decimal('1000000')


class Command(BaseCommand):
    help = 'Import ICPD planning data from the nested ICPD JSON format.'

    def add_arguments(self, parser):
        parser.add_argument('json_file', help='Path to the ICPD planning JSON file.')
        parser.add_argument(
            '--replace',
            action='store_true',
            help='Delete existing ICPD planning data before importing.',
        )

    def handle(self, *args, **options):
        json_path = Path(options['json_file'])
        if not json_path.is_file():
            raise CommandError(f'JSON file not found: {json_path}')

        try:
            payload = json.loads(json_path.read_text(encoding='utf-8'))
        except json.JSONDecodeError as error:
            raise CommandError(f'Invalid JSON: {error}') from error

        commitments = payload.get('commitments')
        if not isinstance(commitments, list):
            raise CommandError('The JSON must contain a "commitments" array.')

        counts = {'commitments': 0, 'objectives': 0, 'activities': 0, 'indicators': 0, 'targets': 0}
        with transaction.atomic():
            if options['replace']:
                Commitment.objects.all().delete()

            for commitment_data in commitments:
                if not options['replace'] and Commitment.objects.filter(
                    title=commitment_data['title'],
                ).exists():
                    self.stdout.write(f'Skipped existing commitment: {commitment_data["title"]}')
                    continue
                commitment = Commitment.objects.create(
                    title=commitment_data['title'],
                    description=commitment_data.get('description', ''),
                    sort_order=commitment_data.get('sort_order', 0),
                    is_active=commitment_data.get('is_active', True),
                )
                counts['commitments'] += 1
                for objective_data in commitment_data.get('objectives', []):
                    objective = Objective.objects.create(
                        commitment=commitment,
                        title=objective_data['title'],
                        description=objective_data.get('description', ''),
                        sort_order=objective_data.get('sort_order', 0),
                    )
                    counts['objectives'] += 1
                    for activity_data in objective_data.get('activities', []):
                        activity = Activity.objects.create(
                            objective=objective,
                            title=activity_data.get('title', activity_data.get('key_action', '')),
                            timeline=activity_data.get('timeline', ''),
                            responsibility=activity_data.get('responsibility', ''),
                            budget_amount=self._to_millions(activity_data.get('budget_amount')),
                            budget_currency=activity_data.get('budget_currency', 'KES'),
                            remarks=activity_data.get('remarks') or '',
                            sort_order=activity_data.get('sort_order', 0),
                        )
                        counts['activities'] += 1
                        indicators = activity_data.get('indicators')
                        if indicators is None and activity_data.get('indicator'):
                            indicators = [{
                                'name': activity_data['indicator'],
                                'annual_targets': [
                                    {'financial_year': year, 'target_value': value}
                                    for year, value in activity_data.get('annual_values', {}).items()
                                ],
                            }]
                        for indicator_data in indicators or []:
                            indicator = ActivityIndicator.objects.create(
                                activity=activity,
                                name=indicator_data['name'],
                                baseline_value=indicator_data.get('baseline_value'),
                                baseline_year=indicator_data.get('baseline_year', ''),
                                notes=indicator_data.get('notes', ''),
                            )
                            counts['indicators'] += 1
                            for target_data in indicator_data.get('annual_targets', []):
                                target_value = self._to_decimal(target_data.get('target_value'))
                                if target_value is None:
                                    continue
                                IndicatorYearData.objects.create(
                                    activity_indicator=indicator,
                                    financial_year=self._normalise_financial_year(target_data['financial_year']),
                                    target_value=target_value,
                                )
                                counts['targets'] += 1

        self.stdout.write(self.style.SUCCESS(
            'Imported {commitments} commitments, {objectives} objectives, {activities} activities, '
            '{indicators} indicators, and {targets} annual targets.'.format(**counts),
        ))

    @staticmethod
    def _to_millions(value):
        if value in (None, ''):
            return None
        return Decimal(str(value)) / KES_PER_MILLION

    @staticmethod
    def _to_decimal(value):
        if value is None:
            return None
        try:
            return Decimal(str(value))
        except InvalidOperation:
            return None

    @staticmethod
    def _normalise_financial_year(value):
        start_year, end_year = value.split('/')
        return f'{start_year}/{end_year[-2:]}'