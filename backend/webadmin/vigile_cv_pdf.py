"""Génération du CV PDF vigile (texte + photo + carte d'identité)."""

from __future__ import annotations

import logging
from io import BytesIO

from django.utils import timezone

logger = logging.getLogger(__name__)


def uploaded_file_kind(file_field) -> str | None:
    if not file_field:
        return None
    name = file_field.name.lower()
    if name.endswith(".pdf"):
        return "pdf"
    if name.endswith((".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".tif", ".tiff")):
        return "image"
    return "file"


def _image_reader_from_field(file_field, *, max_side: int = 1600):
    from PIL import Image, ImageOps
    from reportlab.lib.utils import ImageReader

    if not file_field or uploaded_file_kind(file_field) != "image":
        return None
    try:
        with file_field.open("rb") as handle:
            raw = handle.read()
        img = Image.open(BytesIO(raw))
        img = ImageOps.exif_transpose(img)
        if img.mode not in ("RGB", "L"):
            img = img.convert("RGB")
        longest = max(img.size)
        if longest > max_side:
            scale = max_side / float(longest)
            new_size = (max(1, int(img.width * scale)), max(1, int(img.height * scale)))
            img = img.resize(new_size, Image.Resampling.LANCZOS)
        out = BytesIO()
        img.save(out, format="JPEG", quality=88)
        out.seek(0)
        return ImageReader(out)
    except Exception:
        logger.exception("Impossible de charger l'image pour le CV: %s", file_field.name)
        return None


def _draw_image_fit(pdf, reader, x: float, y_top: float, max_w: float, max_h: float) -> float:
    iw, ih = reader.getSize()
    scale = min(max_w / iw, max_h / ih)
    dw, dh = iw * scale, ih * scale
    y_bottom = y_top - dh
    pdf.drawImage(reader, x, y_bottom, width=dw, height=dh, preserveAspectRatio=True)
    return y_bottom


def _ensure_space(pdf, y: float, needed: float, page_h: float, margin: float) -> float:
    if y - needed >= margin:
        return y
    pdf.showPage()
    return page_h - margin


def _draw_document_block(
    pdf,
    title: str,
    file_field,
    *,
    x: float,
    y: float,
    max_w: float,
    page_h: float,
    margin: float,
    max_img_h: float = 240,
) -> float:
    y = _ensure_space(pdf, y, 40, page_h, margin)
    pdf.setFont("Helvetica-Bold", 11)
    pdf.drawString(x, y, title)
    y -= 14

    if not file_field:
        pdf.setFont("Helvetica-Oblique", 10)
        pdf.drawString(x, y, "Non renseigné")
        return y - 22

    kind = uploaded_file_kind(file_field)
    if kind == "image":
        reader = _image_reader_from_field(file_field)
        if reader:
            y = _ensure_space(pdf, y, max_img_h + 20, page_h, margin)
            y_bottom = _draw_image_fit(pdf, reader, x, y, max_w, max_img_h)
            return y_bottom - 20
        pdf.setFont("Helvetica-Oblique", 10)
        pdf.drawString(x, y, "Image illisible")
        return y - 22

    if kind == "pdf":
        pdf.setFont("Helvetica", 10)
        pdf.drawString(
            x,
            y,
            "Document PDF enregistré — ouvrir la fiche vigile pour le consulter.",
        )
        return y - 22

    pdf.setFont("Helvetica", 10)
    pdf.drawString(x, y, "Fichier présent (aperçu non disponible pour ce format).")
    return y - 22


def build_vigile_cv_pdf(vigile) -> bytes:
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas

    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)
    w, h = A4
    margin = 40
    y = h - margin
    text_right = w - margin - 120

    profile_reader = _image_reader_from_field(vigile.profile_photo)
    if profile_reader:
        _draw_image_fit(pdf, profile_reader, w - margin - 105, y, 105, 130)

    pdf.setTitle(f"CV Vigile - {vigile.display_name}")
    pdf.setFont("Helvetica-Bold", 18)
    pdf.drawString(margin, y, "CV Vigile")
    y -= 24
    pdf.setFont("Helvetica-Bold", 12)
    pdf.drawString(margin, y, (vigile.get_full_name() or "").strip() or vigile.username)
    y -= 28

    def _line(label: str, value: str) -> None:
        nonlocal y
        y = _ensure_space(pdf, y, 22, h, margin)
        pdf.setFont("Helvetica-Bold", 10)
        pdf.drawString(margin, y, f"{label} :")
        pdf.setFont("Helvetica", 10)
        text = value or "—"
        pdf.drawString(190, y, text[:80])
        y -= 18

    _line("Identifiant", vigile.username)
    _line("Rôle", vigile.get_role_display())
    _line("Prénom", vigile.first_name or "—")
    _line("Nom", vigile.last_name or "—")
    _line("Téléphone", vigile.phone_number or "—")
    _line("Email", vigile.email or "—")
    _line("Domicile", vigile.domicile or "—")
    _line("Aval", vigile.aval or "—")
    _line(
        "Date d'intégration",
        vigile.date_integration.strftime("%d/%m/%Y") if vigile.date_integration else "—",
    )
    _line("Taille", f"{vigile.height_cm} cm" if vigile.height_cm else "—")
    _line(
        "Niveau d'études",
        vigile.get_education_level_display() if vigile.education_level else "—",
    )
    _line("Compte actif", "Oui" if vigile.is_active else "Non")
    _line("En service", "Oui" if vigile.is_active_on_duty else "Non")
    _line(
        "Date création compte",
        timezone.localtime(vigile.date_joined).strftime("%d/%m/%Y %H:%M")
        if vigile.date_joined
        else "—",
    )
    _line(
        "Dernière connexion",
        timezone.localtime(vigile.last_login).strftime("%d/%m/%Y %H:%M")
        if vigile.last_login
        else "Jamais",
    )

    y -= 8
    y = _ensure_space(pdf, y, 60, h, margin)
    pdf.setFont("Helvetica-Bold", 14)
    pdf.drawString(margin, y, "Pièces justificatives")
    y -= 26

    y = _draw_document_block(
        pdf,
        "Photo portrait",
        vigile.profile_photo,
        x=margin,
        y=y,
        max_w=text_right - margin,
        page_h=h,
        margin=margin,
        max_img_h=200,
    )
    y = _draw_document_block(
        pdf,
        "Carte d'identité — recto",
        vigile.id_document,
        x=margin,
        y=y,
        max_w=w - 2 * margin,
        page_h=h,
        margin=margin,
    )
    y = _draw_document_block(
        pdf,
        "Carte d'identité — verso",
        vigile.id_document_verso,
        x=margin,
        y=y,
        max_w=w - 2 * margin,
        page_h=h,
        margin=margin,
    )

    pdf.setFont("Helvetica-Oblique", 8)
    pdf.drawString(
        margin,
        30,
        f"Généré le {timezone.localtime().strftime('%d/%m/%Y à %H:%M')} · SMS/Cobra",
    )
    pdf.save()
    buffer.seek(0)
    return buffer.read()
