from django.db import transaction
from django.db.models import Count, Q
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response

from apps.core.csvutil import csv_response
from apps.core.models import AppSettings
from apps.core.workspace import WorkspaceMixin
from apps.sharing.access import lists_for, shared_list_ids, sharers_of_lists

import json

from rest_framework.parsers import JSONParser, MultiPartParser

from .models import Contact, ContactField, ContactList
from .phones import parse_lines
from .validation import summary as validation_summary
from .serializers import BulkSerializer, ContactFieldSerializer, ContactListSerializer, ContactSerializer, ImportSerializer
from .tabular import TableError, apply_columns, field_key, field_labels, guess, read_csv_text, read_upload


class ContactPagination(PageNumberPagination):
    page_size = 50
    page_size_query_param = "page_size"
    max_page_size = 500


def filtered_contacts(owner, params):
    """Own contacts; or, when ?list= is a list shared with this workspace, that list's members (read-only)."""
    qs = Contact.objects.filter(owner=owner)
    if params.get("list") and str(params["list"]).isdigit() and lists_for(owner).filter(pk=params["list"]).exclude(owner=owner).exists():
        qs = Contact.objects.filter(lists__id=params["list"])
    q = (params.get("q") or "").strip()
    if q:
        digits = "".join(ch for ch in q if ch.isdigit())
        cond = Q(name__icontains=q)
        if digits:
            cond |= Q(phone__contains=digits)
        qs = qs.filter(cond)
    if params.get("list"):
        qs = qs.filter(lists__id=params["list"])
    if params.get("opted_out") in ("true", "false"):
        qs = qs.filter(opted_out=params["opted_out"] == "true")
    valid = params.get("valid")
    if valid == "yes":
        qs = qs.filter(on_whatsapp=True)
    elif valid == "no":
        qs = qs.filter(on_whatsapp=False)
    elif valid == "pending":
        qs = qs.filter(checked_at__isnull=True, opted_out=False)
    return qs


class ContactViewSet(WorkspaceMixin, viewsets.ModelViewSet):
    serializer_class = ContactSerializer
    pagination_class = ContactPagination

    def get_queryset(self):
        if self.action not in ("list", "retrieve"):
            return Contact.objects.filter(owner=self.workspace)  # shared contacts can't be changed
        return filtered_contacts(self.workspace, self.request.query_params).prefetch_related("lists")

    def perform_create(self, serializer):
        serializer.save(owner=self.workspace)

    @action(detail=False, methods=["get"])
    def ids(self, request):
        """Every id matching the current filters (for "select all")."""
        return Response(list(filtered_contacts(self.workspace, request.query_params).values_list("id", flat=True)[:50000]))

    @action(detail=False, methods=["get"])
    def export(self, request):
        """Contacts matching the current filters as CSV (same columns the importer reads back)."""
        qs = filtered_contacts(self.workspace, request.query_params).prefetch_related("lists").order_by("name", "phone")
        extra = list(ContactField.objects.filter(owner=self.workspace).values_list("key", "label"))
        rows = ([c.name, "+" + c.phone, ", ".join(l.name for l in c.lists.all()), "yes" if c.opted_out else "",
                 {True: "yes", False: "no", None: "not checked yet"}[c.on_whatsapp], c.checked_at,
                 *(c.fields.get(k, "") for k, _ in extra)]
                for c in qs.iterator(chunk_size=2000))
        header = ["Name", "Phone", "Lists", "Opted out", "On WhatsApp", "Checked", *(label for _, label in extra)]
        return csv_response("contacts.csv", header, rows)

    def _import_data(self, request):
        """request.data as a plain dict; from a file upload, `columns` arrives as a JSON string."""
        data = {k: request.data.get(k) for k in request.data.keys()}
        if "file" in request.FILES:
            data["file"] = request.FILES["file"]
        if isinstance(data.get("columns"), str):
            try:
                data["columns"] = json.loads(data["columns"]) if data["columns"] else []
            except ValueError:
                data["columns"] = None
        for k in ("has_header", "update_names", "list_id", "new_list"):
            if data.get(k) in ("", "null", None):
                data.pop(k, None)
        if not data.get("columns"):
            data.pop("columns", None)
        return data

    def _table(self, d):
        return read_upload(d["file"]) if d.get("file") else read_csv_text(d["text"])

    @action(detail=False, methods=["post"], url_path="import/preview", parser_classes=[JSONParser, MultiPartParser])
    def import_preview(self, request):
        """The file's columns, a few sample rows and a suggested use for each column, for the import screen."""
        s = ImportSerializer(data=self._import_data(request))
        s.is_valid(raise_exception=True)
        d = s.validated_data
        ws = self.workspace
        try:
            rows = self._table(d)
        except TableError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        if not rows:
            return Response({"error": "The file is empty."}, status=status.HTTP_400_BAD_REQUEST)
        width = max(len(r) for r in rows[:200])
        has_header, uses = guess(rows[0] + [""] * (width - len(rows[0])), AppSettings.load(ws).default_country_code)
        headers = rows[0] if has_header else [f"Column {i + 1}" for i in range(width)]
        data_rows = rows[1:] if has_header else rows
        known = set(ContactField.objects.filter(owner=ws).values_list("key", flat=True))
        # Columns named like a field you already use (e.g. Score) default to that field.
        uses = [("field" if u == "ignore" and has_header and field_key(h) in known else u) for u, h in zip(uses, headers + [""] * width)]
        return Response({
            "has_header": has_header,
            "headers": headers + [f"Column {i + 1}" for i in range(len(headers), width)],
            "sample": data_rows[:5],
            "total_rows": len(data_rows),
            "columns": uses,
        })

    @action(detail=False, methods=["post"], url_path="import", parser_classes=[JSONParser, MultiPartParser])
    def import_contacts(self, request):
        s = ImportSerializer(data=self._import_data(request))
        s.is_valid(raise_exception=True)
        d = s.validated_data
        ws = self.workspace
        cc = AppSettings.load(ws).default_country_code

        target_list = None
        if d.get("new_list", "").strip():
            target_list = (ContactList.objects.filter(owner=ws, name__iexact=d["new_list"].strip()).first()
                           or ContactList.objects.create(owner=ws, name=d["new_list"].strip()))
        elif d.get("list_id"):
            target_list = ContactList.objects.filter(pk=d["list_id"], owner=ws).first()

        rows, invalid, columns, extra, labels = {}, [], {}, {}, {}
        if d.get("file") or d.get("columns"):
            # A table with a column chosen for each use (file uploads always come this way).
            try:
                table = self._table(d)
            except TableError as e:
                return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
            if not table:
                return Response({"error": "The file is empty."}, status=status.HTTP_400_BAD_REQUEST)
            has_header, uses = guess(table[0], cc)
            if d.get("columns"):
                uses = d["columns"]
            if d.get("has_header") is not None:
                has_header = d["has_header"]
            labels = field_labels(table, uses, has_header)
            records = apply_columns(table, uses, has_header, cc)
        else:
            records = ((n, p, nm, {}, raw) for n, p, nm, raw in parse_lines(d["text"], cc, columns))
        for line_no, phone, name, values, raw in records:
            if not phone:
                if not (line_no == 1 and not any(ch.isdigit() for ch in raw)):  # skip a header row quietly
                    invalid.append({"line": line_no, "text": raw[:80]})
                continue
            if phone not in rows or (name and not rows[phone]):
                rows[phone] = name
            extra.setdefault(phone, {}).update(values)

        created = updated = 0
        with transaction.atomic():
            mine = Contact.objects.filter(owner=ws)
            existing = {c.phone: c for c in mine.filter(phone__in=rows)}
            new = [Contact(owner=ws, phone=p, name=n, fields=extra.get(p, {})) for p, n in rows.items() if p not in existing]
            Contact.objects.bulk_create(new, batch_size=1000)
            created = len(new)
            if d["update_names"]:
                changed = [c for p, c in existing.items() if rows[p] and c.name != rows[p]]
                for c in changed:
                    c.name = rows[c.phone]
                Contact.objects.bulk_update(changed, ["name"], batch_size=1000)
                updated = len(changed)
            # New values for imported columns replace old ones; columns not in this file are kept.
            refreshed = [c for p, c in existing.items() if extra.get(p) and {**c.fields, **extra[p]} != c.fields]
            for c in refreshed:
                c.fields = {**c.fields, **extra[c.phone]}
            Contact.objects.bulk_update(refreshed, ["fields"], batch_size=1000)
            for key, label in labels.items():
                ContactField.objects.get_or_create(owner=ws, key=key, defaults={"label": label})
            if target_list:
                target_list.contacts.add(*mine.filter(phone__in=rows).values_list("id", flat=True))
        imported = mine.filter(phone__in=rows)
        return Response({
            "total": len(rows), "created": created, "updated": updated, "invalid": invalid[:200],
            "invalid_count": len(invalid), "list": ContactListSerializer(target_list, context={"request": request}).data if target_list else None,
            "validation": validation_summary(imported),
            "columns": columns or None,
            "fields": sorted(labels),
            "fields_updated": len(refreshed),
            # Letters lost before upload (e.g. Bangla in a CSV that Excel saved without UTF-8) arrive as "???".
            "garbled_names": sum(1 for n in rows.values() if "??" in n),
        })

    @action(detail=False, methods=["get"])
    def validation(self, request):
        """How many numbers (matching the filters) are valid, not on WhatsApp, or still being checked."""
        return Response(validation_summary(filtered_contacts(self.workspace, request.query_params)))

    @action(detail=False, methods=["post"])
    def bulk(self, request):
        s = BulkSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        d = s.validated_data
        qs = Contact.objects.filter(owner=self.workspace, pk__in=d["ids"])
        act = d["action"]
        if act == "delete":
            n, _ = qs.delete()
            return Response({"affected": n})
        if act in ("opt_out", "opt_in"):
            return Response({"affected": qs.update(opted_out=act == "opt_out")})
        if act == "recheck":
            return Response({"affected": qs.update(checked_at=None)})
        lst = ContactList.objects.filter(pk=d["list_id"], owner=self.workspace).first()
        if not lst:
            return Response({"error": "That list no longer exists."}, status=status.HTTP_404_NOT_FOUND)
        ids = list(qs.values_list("id", flat=True))
        (lst.contacts.add if act == "add_to_list" else lst.contacts.remove)(*ids)
        return Response({"affected": len(ids)})


class ContactListViewSet(WorkspaceMixin, viewsets.ModelViewSet):
    serializer_class = ContactListSerializer
    pagination_class = None

    def perform_create(self, serializer):
        serializer.save(owner=self.workspace)

    def get_queryset(self):
        base = lists_for(self.workspace) if self.action in ("list", "retrieve") else ContactList.objects.filter(owner=self.workspace)
        return ContactList.objects.filter(pk__in=base.values("pk")).select_related("owner").annotate(
            contact_count=Count("contacts", filter=Q(contacts__opted_out=False) & ~Q(contacts__on_whatsapp=False)))


class ContactFieldViewSet(WorkspaceMixin, viewsets.ModelViewSet):
    """Extra columns usable in messages, e.g. {score}. Made by imports, or added by hand in the template editor."""

    serializer_class = ContactFieldSerializer
    pagination_class = None
    http_method_names = ["get", "post", "delete"]

    def get_queryset(self):
        if self.action == "list":
            # Fields of people who shared a contact list come along, so their columns work in messages.
            return ContactField.objects.filter(Q(owner=self.workspace) | Q(owner__in=sharers_of_lists(self.workspace))).select_related("owner")
        return ContactField.objects.filter(owner=self.workspace)

    def perform_create(self, serializer):
        serializer.save(owner=self.workspace, key=field_key(serializer.validated_data["label"]))
