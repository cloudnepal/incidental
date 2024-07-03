from abc import abstractmethod

from sqlalchemy.orm import Session

from app.models import Organisation
from app.repos import FormRepo, IncidentRepo, SeverityRepo, UserRepo
from app.schemas.slack import SlackCommandDataSchema
from app.services.events import Events
from app.services.factories import create_incident_service, create_slack_user_service


class SlackCommandHandlerBase:
    trigger_word = "override-this"
    trigger_in_incident_channel = True

    def __init__(self, session: Session, organisation: Organisation, events: Events) -> None:
        self.session = session
        self.organisation = organisation
        self.events = events

        # setup common repos
        self.form_repo = FormRepo(session=self.session)
        self.severity_repo = SeverityRepo(session=self.session)
        self.incident_repo = IncidentRepo(session=self.session)
        self.user_repo = UserRepo(session=self.session)

        # services
        self.incident_service = create_incident_service(session=session, organisation=organisation, events=events)
        self.slack_user_service = create_slack_user_service(session=session)

    @abstractmethod
    def execute(self, command: SlackCommandDataSchema):
        raise NotImplementedError()

    def get_params(self, command: SlackCommandDataSchema) -> tuple[str, list[str]]:
        if not command.text:
            return []

        parts = list(map(lambda it: it.strip(), command.text.split(" ")))
        return parts[0], parts[1:]

    def _is_incident_channel(self, channel_id: str) -> bool:
        """Is the slack channel associated with an incident"""
        incidents = self.incident_repo.get_all_incidents(organisation=self.organisation)
        channel_ids = set([it.slack_channel_id for it in incidents])

        if channel_id in channel_ids:
            return True

        return False

    def can_trigger(self, command: SlackCommandDataSchema) -> bool:
        """Only trigger this if in an incident channel"""

        lead, _ = self.get_params(command=command)

        # does not match trigger word
        if self.trigger_word != lead:
            return False

        # if command should run in incident channel
        if self._is_incident_channel(command.channel_id) and self.trigger_in_incident_channel:
            return True

        # if command should be run outside incident channel
        if not self._is_incident_channel(command.channel_id) and not self.trigger_in_incident_channel:
            return True

        return False