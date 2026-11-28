from typing import Optional, Dict, Any, List
from uuid import UUID
from sqlalchemy import desc, or_, asc
from fastapi import HTTPException

from app.services.base import BaseService
from app.models.template import TemplateCollection, TemplateCollectionItem


class TemplateCollectionService(BaseService):

    def create_collection(self, user_id: int, name: str, description: Optional[str] = None,
                          is_public: bool = False) -> TemplateCollection:

        collection = TemplateCollection(
            name=name,
            description=description,
            created_by_user_id=user_id,
            is_public=is_public
        )

        self.db.add(collection)
        self.db.commit()
        self.db.refresh(collection)

        return collection

    def add_to_collection(self, collection_id: UUID, template_id: UUID, user_id: int,
                          order_index: int = 0) -> TemplateCollectionItem:

        collection = self.db.query(TemplateCollection).filter(
            TemplateCollection.id == collection_id,
            TemplateCollection.created_by_user_id == user_id
        ).first()

        if not collection:
            raise HTTPException(status_code=403, detail="No permission to modify this collection")

        existing = self.db.query(TemplateCollectionItem).filter(
            TemplateCollectionItem.collection_id == collection_id,
            TemplateCollectionItem.template_id == template_id
        ).first()

        if existing:
            raise HTTPException(status_code=400, detail="Template already in collection")

        item = TemplateCollectionItem(
            collection_id=collection_id,
            template_id=template_id,
            order_index=order_index,
            added_by_user_id=user_id
        )

        self.db.add(item)
        collection.template_count += 1

        self.db.commit()
        self.db.refresh(item)

        return item

    def get_user_collections(self, user_id: int, include_public: bool = True) -> List[TemplateCollection]:

        query = self.db.query(TemplateCollection).filter(
            TemplateCollection.created_by_user_id == user_id
        )

        if include_public:
            query = query.filter(
                or_(
                    TemplateCollection.created_by_user_id == user_id,
                    TemplateCollection.is_public == True
                )
            )

        return query.order_by(desc(TemplateCollection.updated_at)).all()
