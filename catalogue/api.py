import traceback
from rest_framework import serializers, viewsets, status
from rest_framework.response import Response
from rest_framework.fields import empty
import base64
from django.core.files.base import ContentFile
import json
from django.conf import settings
from pycsw.core import util
from django.http import HttpResponse, JsonResponse
from .models import Record, Style
from catalogue import models as catalogue_models


# Ows Resource Serializer
class OwsResourceSerializer(serializers.Serializer):
    wfs = serializers.BooleanField(write_only=True, default=False)
    wfs_endpoint = serializers.CharField(write_only=True, allow_null=True, default=None)
    wfs_version = serializers.CharField(write_only=True, allow_null=True, default=None)
    wms = serializers.BooleanField(write_only=True, default=False)
    wms_endpoint = serializers.CharField(write_only=True, allow_null=True, default=None)
    wms_version = serializers.CharField(write_only=True, allow_null=True, default=None)
    gwc = serializers.BooleanField(write_only=True, default=False)
    gwc_endpoint = serializers.CharField(write_only=True, allow_null=True, default=None)

    def run_validation(self, data=empty):
        result = super(OwsResourceSerializer, self).run_validation(data)
        if ((data.get('wfs', False) and (not data['wfs_endpoint'] or not data['wfs_version'])) or
            (data.get('wms', False) and (not data['wms_endpoint'] or not data['wms_version'])) or
                (data.get('gwc', False) and not data['gwc_endpoint'])):
            raise serializers.ValidationError(
                "Both endpoint and version must have value if service is enabled.")
        elif (data.get('gwc', False) and not data['wms']):
            raise serializers.ValidationError("WMS must be enabled if gwc is enabled.")

        return result

    def get_links(self, record, validated_data):
        links = []
        if validated_data['gwc']:
            gwc_endpoints = [
                endpoint.strip() for endpoint in validated_data['gwc_endpoint'].split("^") if endpoint.strip()]
            for endpoint in gwc_endpoints:
                links.append(
                    record.generate_ows_link(endpoint, 'GWC', validated_data['wms_version'])
                )
        elif validated_data['wms']:
            links.append(
                record.generate_ows_link(
                    validated_data['wms_endpoint'],
                    'WMS',
                    validated_data['wms_version'])
            )
        if validated_data['wfs']:
            links.append(
                record.generate_ows_link(
                    validated_data['wfs_endpoint'],
                    'WFS',
                    validated_data['wfs_version'])
            )
        if record.service_type == "WMS":
            record.service_type_version = validated_data['wms_version']
        elif record.service_type == "WFS":
            record.service_type_version = validated_data['wfs_version']
        else:
            record.service_type_version = ""

        style_links = record.style_links
        resources = links + style_links

        return record.format_links(resources)


# Style Serializer
class StyleSerializer(serializers.ModelSerializer):
    content = serializers.CharField(write_only=True, allow_null=True)
    name = serializers.CharField(default=Style.BUILTIN)

    def get_raw_content(self, obj):
        if obj.content:
            return base64.b64encode(obj.content.read())
        else:
            return None

    def __init__(self, *args, **kwargs):
        try:
            style_content = kwargs.pop("style_content")
        except BaseException:
            style_content = False

        super(StyleSerializer, self).__init__(*args, **kwargs)
        if style_content:
            self.fields['raw_content'] = serializers.SerializerMethodField(read_only=True)

    def run_validation(self, data=empty):
        return super(StyleSerializer, self).run_validation(data)

    class Meta:
        model = Style
        fields = (
            'name',
            'format',
            'default',
            'content',
        )


class LegendSerializer(serializers.Serializer):
    content = serializers.CharField(write_only=True, allow_null=False)
    ext = serializers.CharField(write_only=True, allow_null=False)

    def run_validation(self, data=empty):
        return super(LegendSerializer, self).run_validation(data)


# Record Serializer
class RecordSerializer(serializers.ModelSerializer):
    workspace = serializers.CharField(max_length=255, write_only=True)
    name = serializers.CharField(max_length=255, write_only=True)
    id = serializers.IntegerField(read_only=True)
    identifier = serializers.CharField(max_length=255, read_only=True)
    url = serializers.SerializerMethodField(read_only=True)
    publication_date = serializers.DateTimeField(format='%Y-%m-%d %H:%M:%S.%f')
    modified = serializers.DateTimeField(
        format='%Y-%m-%d %H:%M:%S.%f',
        allow_null=True,
        default=None)
    metadata_link = serializers.SerializerMethodField(read_only=True)
    tags = serializers.SerializerMethodField(read_only=True)
    source_legend = LegendSerializer(write_only=True, allow_null=True, required=False)
    legend = serializers.SerializerMethodField(read_only=True)
    links = serializers.CharField(write_only=True, allow_null=True, required=False)

    def __init__(self, *args, **kwargs):
        self.request = kwargs["context"]["request"] if "context" in kwargs and "request" in kwargs["context"] else None
        try:
            style_content = kwargs.pop("style_content")
        except BaseException:
            style_content = False
        try:
            ows_serialize_direction = kwargs.pop('serialize_direction')
        except BaseException:
            ows_serialize_direction = 'read'

        super(RecordSerializer, self).__init__(*args, **kwargs)
        self.fields['styles'] = StyleSerializer(
            many=True, required=False, style_content=style_content)
        if ows_serialize_direction == 'write':
            self.fields['ows_resource'] = OwsResourceSerializer(write_only=True, required=False)
        elif ows_serialize_direction == 'read':
            self.fields['ows_resource'] = serializers.SerializerMethodField(read_only=True)

    def is_valid(self, raise_exception=False):
        super(RecordSerializer, self).is_valid(raise_exception)
        # transform the bbox data format
        if self.validated_data.get('bounding_box'):
            bounding_box = json.loads(self.validated_data['bounding_box'])
            bounding_box = ','.join([str(o) for o in bounding_box])
            try:
                self.validated_data['bounding_box'] = util.bbox2wktpolygon(bounding_box)
            except BaseException:
                traceback.print_exc()
                raise serializers.ValidationError("Incorrect bounding box dataformat.")

    def run_validation(self, data=empty):
        return super(RecordSerializer, self).run_validation(data)

    def save(self, **kwargs):
        self.validated_data['identifier'] = "{}:{}".format(
            self.validated_data['workspace'], self.validated_data['name'])
        # remove fake fields
        if "workspace" in self.validated_data:
            self.validated_data.pop("workspace")
        if "name" in self.validated_data:
            self.validated_data.pop("name")

        try:
            self.instance = Record.objects.get(identifier=self.validated_data["identifier"])
            self.instance.active = True

            for key in ["title", "abstract", "modified", "insert_date"]:
                if key in self.validated_data:
                    self.validated_data.pop(key)
            self.new_record = False

        except Record.DoesNotExist:
            # record does not exist, create it
            self.new_record = True

        # update source legend
        source_legend = self.validated_data.pop(
            "source_legend") if "source_legend" in self.validated_data else None
        if source_legend:
            tmpRecord = Record(identifier=self.validated_data["identifier"])
            tmpRecord.source_legend.save(
                "upload{}".format(
                    source_legend.get(
                        "ext", "")), ContentFile(
                    base64.b64decode(
                        source_legend["content"])), save=False)
            self.validated_data["source_legend"] = tmpRecord.source_legend.name
        elif self.instance and self.instance.source_legend:
            self.instance.source_legend.delete(save=False)
            self.validated_data["source_legend"] = None

        styles_data = self.validated_data.pop("styles") if "styles" in self.validated_data else None
        ows_resource_validated_data = self.validated_data.pop("ows_resource")
        if self.instance:
            tmp_instance = Record.objects.get(identifier=self.validated_data["identifier"])
            for attr, value in self.validated_data.items():
                setattr(tmp_instance, attr, value)
        else:
            tmp_instance = Record(**self.validated_data)
        self.validated_data["links"] = self.fields["ows_resource"].get_links(
            tmp_instance, ows_resource_validated_data)
        result = super(RecordSerializer, self).save(**kwargs)
        # save styles
        if styles_data:
            self._update_styles(styles_data)
        return result

    def get_tags(self, obj):
        return obj.tags.values("name", "description")

    def get_ows_resource(self, obj):
        return obj.ows_resource

    def get_metadata_link(self, obj):
        return obj.metadata_link(self.request)

    def get_legend(self, obj):
        if obj.legend or obj.source_legend:
            return '{}{}'.format(settings.BASE_URL, (obj.legend or obj.source_legend).url)
        else:
            return None

    def get_url(self, obj):
        return '{}{}'.format(settings.BASE_URL, '/catalogue/api/records/{0}.json'.format(obj.identifier))

    def _update_styles(self, styles_data):
        # save the style to file system with specific file name
        tmpStyle = Style(record=self.instance, name=Style.BUILTIN, content=None)
        for uploaded_style in styles_data:
            uploaded_style["record"] = self.instance
            uploaded_style["name"] = Style.BUILTIN
            tmpStyle.format = uploaded_style["format"]
            tmpStyle.content.save(
                "",
                ContentFile(
                    base64.b64decode(
                        uploaded_style["content"])),
                save=False)
            uploaded_style["content"] = tmpStyle.content.name

        # get the default style
        origin_default_style = {
            "sld": self.instance.sld.name if self.instance.sld else None,
            "qml": self.instance.qml.name if self.instance.qml else None,
            "lyr": self.instance.lyr.name if self.instance.lyr else None
        }
        default_style = {}
        for uploaded_style in styles_data:
            if uploaded_style.get("default", False):
                # user set this style as default style, use the user's setting
                default_style[uploaded_style["format"]] = uploaded_style
            elif origin_default_style.get(uploaded_style["format"].lower(), None) == uploaded_style["name"]:
                # the current style is configured as default style.
                default_style[uploaded_style["format"]] = uploaded_style
            elif not origin_default_style.get(uploaded_style["format"].lower(), None) and uploaded_style["format"] not in default_style:
                # no default style has been set, set the current style as the default style
                default_style[uploaded_style["format"]] = uploaded_style
            # clear the default flag
            uploaded_style["default"] = False

        # set the default style
        for uploaded_style in iter(default_style.values()):
            uploaded_style["default"] = True

        # save style
        styleSerializer = self.fields["styles"].child
        styleSerializer._errors = []
        for uploaded_style in styles_data:
            styleSerializer._validated_data = uploaded_style
            try:
                styleSerializer.instance = Style.objects.get(
                    record=self.instance,
                    format=uploaded_style["format"].upper(),
                    name=uploaded_style["name"])
            except Style.DoesNotExist:
                styleSerializer.instance = None
            styleSerializer.save()

    class Meta:
        model = Record
        fields = (
            'id',
            'url',
            'identifier',
            'title',
            'insert_date',
            'any_text',
            'modified',
            'abstract',
            'keywords',
            'bounding_box',
            'crs',
            'publication_date',
            'service_type',
            'service_type_version',
            'ows_resource',
            'metadata_link',
            'styles',
            'workspace',
            'legend',
            'source_legend',
            'name',
            'tags',
            'links',
        )


class RecordViewSet(viewsets.ModelViewSet):
    queryset = Record.objects.all()
    serializer_class = RecordSerializer
    authentication_classes = []
    lookup_field = "identifier"
    filter_fields = ('application__name',)

    def perform_destroy(self, instance):
        instance.active = False
        instance.save()

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        style_content = bool(request.GET.get("style_content", False))
        serializer = self.get_serializer(
            instance,
            style_content=style_content,
            serialize_direction='read')
        return Response(serializer.data)

    def create(self, request):
        try:
            http_status = status.HTTP_200_OK
            # parse and valid record data
            serializer = self.get_serializer(data=request.data, serialize_direction='write')
            serializer.is_valid(raise_exception=True)
            # save record data.
            record = serializer.save()
            if serializer.new_record:
                http_status = status.HTTP_201_CREATED

            # return json data
            record.styles.set(list(Style.objects.filter(record=record)))
            style_content = bool(request.GET.get("style_content", False))
            serializer = self.get_serializer(
                record, style_content=style_content, serialize_direction='read')
            return Response(serializer.data, status=http_status)
        except serializers.ValidationError:
            raise
        except Exception as e:
            traceback.print_exc()


def application_record(request):
    rows=[]
    application_name = request.GET.get("application__name", None)
    if application_name:
        application = catalogue_models.Application.objects.filter(name=application_name)
        if application.count() > 0:
            first_record = application[0]
            for ar in first_record.records.all():
                row = {}
                row['abstract'] = ar.abstract
                row['any_text'] = ar.any_text
                row['bounding_box'] = ar.bounding_box
                row['crs'] = ar.crs
                row['id'] = ar.id
                row['identifier'] = ar.identifier
                row['insert_date'] = str(ar.insert_date)
                row['keywords'] = ar.keywords
                row['legend'] = ''

                if ar.legend:
                    row['legend'] = request.build_absolute_uri(ar.legend.url)
                row['metadata_link'] = {'endpoint': '', 'link': '', 'type': '', 'version': ''} 
                if ar.metadata_link:
                    row['metadata_link'] = ar.metadata_link(request)
                row['modified'] = str(ar.modified)
                row['ows_resource'] =  ar.ows_resource
                row['publication_date'] = str(ar.publication_date)
                row['service_type'] = ar.service_type
                row['service_type_version'] = ar.service_type_version
                row['styles'] = []
                row['tags'] = []
                for t in ar.tags.all():
                    tag_row = {'description': t.description, 'name': t.name}
                    row['tags'].append(tag_row)

                row['title'] = ar.title
                row['url'] = '{}{}'.format(settings.BASE_URL, '/catalogue/api/records/{0}.json'.format(ar.identifier)) 
                rows.append(row)

    response = HttpResponse(json.dumps(rows), content_type='application/json')
    response['Access-Control-Allow-Origin'] = '*'
    response['Access-Control-Allow-Credentials'] = 'true'
    response['Access-Control-Allow-Headers'] '*'
    return response


