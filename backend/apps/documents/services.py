from __future__ import annotations

import hashlib
import uuid
from io import BytesIO

from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from PIL import Image, ImageOps

from apps.companies.limits import enforce_upload_limits
from apps.expenses.models import VehicleExpense, VehicleExpenseAttachment

from .models import Attachment, DriverLicense, DriverLicenseAttachment, VehicleDocument, VehicleDocumentAttachment

SUPPORTED_IMAGE_FORMATS = {"JPEG", "PNG", "WEBP"}
MAX_IMAGE_SIDE = 1600
JPEG_QUALITY = 75


def compress_and_store_document_image(
    *,
    company_id: int,
    uploaded_file,
    storage_prefix: str,
    actor_id: int | None = None,
    replacing_size_bytes: int = 0,
) -> Attachment:
    image_bytes = _compress_uploaded_image(uploaded_file)
    enforce_upload_limits(
        company_id=company_id,
        actor_id=actor_id,
        incoming_size_bytes=len(image_bytes),
        replacing_size_bytes=replacing_size_bytes,
    )
    storage_key = f"{storage_prefix}/{company_id}/{uuid.uuid4().hex}.jpg"
    default_storage.save(storage_key, ContentFile(image_bytes))
    return Attachment.objects.create(
        company_id=company_id,
        storage_key=storage_key,
        original_name=getattr(uploaded_file, "name", ""),
        size_bytes=len(image_bytes),
        mime_type="image/jpeg",
        sha256=hashlib.sha256(image_bytes).hexdigest(),
    )


def validate_support_image(uploaded_file):
    uploaded_file.seek(0)
    try:
        with Image.open(uploaded_file) as image:
            if image.format not in SUPPORTED_IMAGE_FORMATS:
                raise ValidationError("Solo se permiten imagenes JPG, PNG o WEBP.")
    except OSError as exc:
        raise ValidationError("No fue posible procesar la imagen subida.") from exc
    finally:
        uploaded_file.seek(0)


def replace_vehicle_document_attachment(*, document: VehicleDocument, uploaded_file, actor_id: int | None = None) -> Attachment:
    return _replace_attachment_for_parent(
        parent=document,
        link_model=VehicleDocumentAttachment,
        relation_field="vehicle_document",
        storage_prefix="documents/vehicle-documents",
        uploaded_file=uploaded_file,
        actor_id=actor_id,
    )


def replace_driver_license_attachment(*, license_doc: DriverLicense, uploaded_file, actor_id: int | None = None) -> Attachment:
    return _replace_attachment_for_parent(
        parent=license_doc,
        link_model=DriverLicenseAttachment,
        relation_field="driver_license",
        storage_prefix="documents/driver-licenses",
        uploaded_file=uploaded_file,
        actor_id=actor_id,
    )


def replace_vehicle_expense_attachment(*, expense: VehicleExpense, uploaded_file, actor_id: int | None = None) -> Attachment:
    return _replace_attachment_for_parent(
        parent=expense,
        link_model=VehicleExpenseAttachment,
        relation_field="vehicle_expense",
        storage_prefix="expenses/vehicle-expenses",
        uploaded_file=uploaded_file,
        actor_id=actor_id,
    )


def _compress_uploaded_image(uploaded_file) -> bytes:
    validate_support_image(uploaded_file)
    uploaded_file.seek(0)
    with Image.open(uploaded_file) as image:

        image = ImageOps.exif_transpose(image)
        if image.mode not in ("RGB", "L"):
            alpha = image.convert("RGBA")
            background = Image.new("RGBA", alpha.size, (255, 255, 255, 255))
            image = Image.alpha_composite(background, alpha).convert("RGB")
        elif image.mode == "L":
            image = image.convert("RGB")

        image.thumbnail((MAX_IMAGE_SIDE, MAX_IMAGE_SIDE), Image.Resampling.LANCZOS)

        output = BytesIO()
        image.save(output, format="JPEG", quality=JPEG_QUALITY, optimize=True, progressive=True)
        return output.getvalue()


def _replace_attachment_for_parent(*, parent, link_model, relation_field: str, storage_prefix: str, uploaded_file, actor_id: int | None = None) -> Attachment:
    old_links = list(
        link_model.objects.select_related("attachment")
        .filter(**{relation_field: parent})
        .order_by("-id")
    )
    old_attachments = [link.attachment for link in old_links]
    replacing_size_bytes = sum(attachment.size_bytes for attachment in old_attachments)

    attachment = compress_and_store_document_image(
        company_id=parent.company_id,
        uploaded_file=uploaded_file,
        storage_prefix=storage_prefix,
        actor_id=actor_id,
        replacing_size_bytes=replacing_size_bytes,
    )

    if old_links:
        link_model.objects.filter(id__in=[link.id for link in old_links]).delete()
        for old_attachment in old_attachments:
            _delete_attachment_if_orphan(old_attachment)

    link_model.objects.create(
        company_id=parent.company_id,
        attachment=attachment,
        **{relation_field: parent},
    )
    return attachment


def _delete_attachment_if_orphan(attachment: Attachment | None):
    if attachment is None:
        return
    if attachment.vehicle_document_links.exists():
        return
    if attachment.driver_license_links.exists():
        return
    if attachment.expense_links.exists():
        return
    if attachment.storage_key and default_storage.exists(attachment.storage_key):
        default_storage.delete(attachment.storage_key)
    attachment.delete()
