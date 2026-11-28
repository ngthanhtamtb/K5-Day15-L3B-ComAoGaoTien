from sqlalchemy.orm import Session

from app.services.presentations.core import PresentationCoreService
from app.services.presentations.pages import PageService
from app.services.presentations.collaboration import CollaborationService
from app.services.presentations.comments import CommentService
from app.services.presentations.sharing import SharingService


class PresentationService:
    def __init__(self, db: Session):
        self.db = db
        self.core = PresentationCoreService(db)
        self.pages = PageService(db)
        self.collaboration = CollaborationService(db)
        self.comments = CommentService(db)
        self.sharing = SharingService(db)

    def create_presentation(self, *args, **kwargs):
        return self.core.create(*args, **kwargs)

    def get_presentation(self, *args, **kwargs):
        return self.core.get(*args, **kwargs)

    # def get_user_presentations(self, *args, **kwargs):
    #     return self.core.get(*args, **kwargs)

    def update_presentation(self, *args, **kwargs):
        return self.core.update(*args, **kwargs)

    def delete_presentation(self, *args, **kwargs):
        return self.core.delete(*args, **kwargs)

    def list_presentations(self, *args, **kwargs):
        return self.core.list_user_presentations(*args, **kwargs)

    def clone_presentation(self, *args, **kwargs):
        return self.core.clone(*args, **kwargs)

    def get_presentation_pages(self, *args, **kwargs):
        return self.pages.get_pages(*args, **kwargs)

    def create_page(self, *args, **kwargs):
        return self.pages.create(*args, **kwargs)

    def update_page(self, *args, **kwargs):
        return self.pages.update(*args, **kwargs)

    def delete_page(self, *args, **kwargs):
        return self.pages.delete(*args, **kwargs)

    def invite_collaborator(self, *args, **kwargs):
        return self.collaboration.invite(*args, **kwargs)

    def accept_collaboration(self, *args, **kwargs):
        return self.collaboration.accept_invitation(*args, **kwargs)

    def remove_collaborator(self, *args, **kwargs):
        return self.collaboration.remove_collaborator(*args, **kwargs)

    def list_collaborators(self, *args, **kwargs):
        return self.collaboration.list_collaborators(*args, **kwargs)

    def create_comment(self, *args, **kwargs):
        return self.comments.create(*args, **kwargs)

    def get_comments(self, *args, **kwargs):
        return self.comments.get_comments(*args, **kwargs)

    def resolve_comment(self, *args, **kwargs):
        return self.comments.resolve(*args, **kwargs)

    def create_share(self, *args, **kwargs):
        return self.sharing.create_share(*args, **kwargs)

    def access_shared_presentation(self, *args, **kwargs):
        return self.sharing.access_shared(*args, **kwargs)