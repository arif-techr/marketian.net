from rest_framework import serializers

from apps.core.models import AppSettings
from apps.core.workspace import workspace_of

from .models import Contact, ContactField, ContactList
from .phones import normalize
from .tabular import MAX_COLS, USES, field_key

MAX_IMPORT_BYTES = 5_000_000
RESERVED_KEYS = {"name", "phone"}


class WorkspaceSerializer(serializers.ModelSerializer):
    @property
    def workspace(self):
        return workspace_of(self.context["request"].user)


class SharedByMixin:
    def get_shared_by(self, obj):
        return obj.owner.username if obj.owner_id != self.workspace.pk else None


class ContactListSerializer(SharedByMixin, WorkspaceSerializer):
    contact_count = serializers.IntegerField(read_only=True, default=0)
    shared_by = serializers.SerializerMethodField()

    class Meta:
        model = ContactList
        fields = ["id", "name", "contact_count", "shared_by", "created_at"]

    def validate_name(self, v):
        v = v.strip()
        if not v:
            raise serializers.ValidationError("Give the list a name.")
        clash = ContactList.objects.filter(owner=self.workspace, name__iexact=v)
        if self.instance:
            clash = clash.exclude(pk=self.instance.pk)
        if clash.exists():
            raise serializers.ValidationError(f'You already have a list called "{v}".')
        return v


class OwnListsField(serializers.PrimaryKeyRelatedField):
    """Only lists in the request's workspace can be picked."""

    def get_queryset(self):
        return ContactList.objects.filter(owner=workspace_of(self.context["request"].user))


class ContactSerializer(SharedByMixin, WorkspaceSerializer):
    lists = OwnListsField(many=True, required=False)
    shared_by = serializers.SerializerMethodField()

    class Meta:
        model = Contact
        fields = ["id", "phone", "name", "lists", "fields", "opted_out", "on_whatsapp", "checked_at", "shared_by", "created_at", "updated_at"]
        read_only_fields = ["on_whatsapp", "checked_at", "created_at", "updated_at"]
        extra_kwargs = {"phone": {"validators": []}}  # uniqueness is checked after normalising

    def validate_phone(self, v):
        phone = normalize(v, AppSettings.load(self.workspace).default_country_code)
        if not phone:
            raise serializers.ValidationError("That doesn't look like a phone number. Include the country code, e.g. +8801712345678.")
        clash = Contact.objects.filter(owner=self.workspace, phone=phone)
        if self.instance:
            clash = clash.exclude(pk=self.instance.pk)
        if clash.exists():
            raise serializers.ValidationError(f"+{phone} is already in your contacts.")
        return phone

    def update(self, instance, validated):
        if "phone" in validated and validated["phone"] != instance.phone:
            # A new number has to be checked again.
            instance.on_whatsapp, instance.wa_jid, instance.checked_at = None, "", None
        return super().update(instance, validated)


class ImportSerializer(serializers.Serializer):
    text = serializers.CharField(max_length=2_000_000, trim_whitespace=False, required=False, allow_blank=True)
    file = serializers.FileField(required=False, max_length=255)
    # What each column is for (from the import screen); empty = work it out from the headings.
    columns = serializers.ListField(child=serializers.ChoiceField(choices=USES), required=False, max_length=MAX_COLS)
    has_header = serializers.BooleanField(required=False, allow_null=True, default=None)
    list_id = serializers.IntegerField(required=False, allow_null=True)
    new_list = serializers.CharField(max_length=80, required=False, allow_blank=True)
    update_names = serializers.BooleanField(default=True)

    def validate(self, attrs):
        if not attrs.get("file") and not (attrs.get("text") or "").strip():
            raise serializers.ValidationError({"text": "Paste some numbers or choose a file."})
        f = attrs.get("file")
        if f and f.size > MAX_IMPORT_BYTES:
            raise serializers.ValidationError({"file": f"Files can be up to {MAX_IMPORT_BYTES // 1_000_000} MB. Split it into smaller files."})
        cols = attrs.get("columns")
        if cols and cols.count("phone") == 0:
            raise serializers.ValidationError({"columns": "Pick the column that has the phone numbers."})
        return attrs


class ContactFieldSerializer(SharedByMixin, WorkspaceSerializer):
    shared_by = serializers.SerializerMethodField()

    class Meta:
        model = ContactField
        fields = ["id", "key", "label", "shared_by", "created_at"]
        read_only_fields = ["key", "created_at"]

    def validate_label(self, v):
        v = v.strip()
        if not v:
            raise serializers.ValidationError("Give the field a name, e.g. Score.")
        key = field_key(v)
        if key in RESERVED_KEYS:
            raise serializers.ValidationError(f"{{{key}}} is built in already.")
        if ContactField.objects.filter(owner=self.workspace, key=key).exists():
            raise serializers.ValidationError(f"You already have the field {{{key}}}.")
        return v


class BulkSerializer(serializers.Serializer):
    ACTIONS = ["delete", "add_to_list", "remove_from_list", "opt_out", "opt_in", "recheck"]
    action = serializers.ChoiceField(choices=ACTIONS)
    ids = serializers.ListField(child=serializers.IntegerField(), max_length=50000)
    list_id = serializers.IntegerField(required=False, allow_null=True)

    def validate(self, attrs):
        if attrs["action"] in ("add_to_list", "remove_from_list") and not attrs.get("list_id"):
            raise serializers.ValidationError({"list_id": "Pick a list."})
        return attrs
