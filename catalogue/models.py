import json
import math
import os
import re

import pyproj
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator
from django.db import models
from django.db.models.signals import post_delete, post_save, pre_save
from django.dispatch import receiver

slug_re = re.compile(r"^[a-z0-9_]+$")
validate_slug = RegexValidator(
    slug_re,
    "Slug can only contain lowercase letters, numbers and underscores",
    "invalid",
)


class PreviewTile(object):
    @staticmethod
    def _preview_tile(max_tile_bbox, max_zoom, bbox):
        # compute the tile which can cover the whole bbox
        tile_bbox = list(max_tile_bbox)
        zoom_level = 1
        while zoom_level <= max_zoom:
            if (
                bbox[0] - tile_bbox[0] < (tile_bbox[2] - tile_bbox[0]) / 2 and bbox[2] - tile_bbox[0] >= (tile_bbox[2] - tile_bbox[0]) / 2
            ) or (
                bbox[1] - tile_bbox[1] < (tile_bbox[3] - tile_bbox[1]) / 2 and bbox[3] - tile_bbox[1] >= (tile_bbox[3] - tile_bbox[1]) / 2
            ):
                break
            if bbox[0] - tile_bbox[0] < (tile_bbox[2] - tile_bbox[0]) / 2:
                tile_bbox[2] = tile_bbox[0] + (tile_bbox[2] - tile_bbox[0]) / 2
            else:
                tile_bbox[0] = tile_bbox[0] + (tile_bbox[2] - tile_bbox[0]) / 2

            if bbox[1] - tile_bbox[1] < (tile_bbox[3] - tile_bbox[1]) / 2:
                tile_bbox[3] = tile_bbox[1] + (tile_bbox[3] - tile_bbox[1]) / 2
            else:
                tile_bbox[1] = tile_bbox[1] + (tile_bbox[3] - tile_bbox[1]) / 2
            zoom_level += 1

        return tile_bbox

    @staticmethod
    def EPSG_4326(bbox):
        # compute the tile which can cover the whole bbox
        # gridset bound [-180, -90, 180, 90]
        return PreviewTile._preview_tile([0, -90, 180, 90], 14, bbox)

    @staticmethod
    def EPSG_3857(bbox):
        # compute the tile which can cover the whole bbox
        # gridset bound [-20, 037, 508.34, -20, 037, 508.34, 20, 037, 508.34, 20, 037, 508.34]
        return PreviewTile._preview_tile([-20037508.34, -20037508.34, 20037508.34, 20037508.34], 14, bbox)


class PycswConfig(models.Model):
    language = models.CharField(max_length=10, default="en-US")
    max_records = models.IntegerField(default=10)
    # log_level  # can use django's config
    # log_file  # can use django's config
    # ogc_schemas_base
    # federated_catalogues
    # pretty_print
    # gzip_compress_level
    # domain_query_type
    # domain_counts
    # spatial_ranking
    transactions = models.BooleanField(default=False, help_text="Enable transactions")
    allowed_ips = models.CharField(
        max_length=255, blank=True, default="127.0.0.1", help_text="IP addresses that are allowed to make transaction requests"
    )
    harvest_page_size = models.IntegerField(default=10)
    title = models.CharField(max_length=50)
    abstract = models.TextField()
    keywords = models.CharField(max_length=255)
    keywords_type = models.CharField(max_length=255)
    fees = models.CharField(max_length=100)
    access_constraints = models.CharField(max_length=255)
    point_of_contact = models.ForeignKey("Collaborator", on_delete=models.PROTECT)
    repository_filter = models.CharField(max_length=255, blank=True)
    inspire_enabled = models.BooleanField(default=False)
    inspire_languages = models.CharField(max_length=255, blank=True)
    inspire_default_language = models.CharField(max_length=30, blank=True)
    inspire_date = models.DateTimeField(null=True, blank=True)
    gemet_keywords = models.CharField(max_length=255, blank=True)
    conformity_service = models.CharField(max_length=255, blank=True)
    temporal_extent_start = models.DateTimeField(null=True, blank=True)
    temporal_extent_end = models.DateTimeField(null=True, blank=True)
    service_type_version = models.CharField(max_length=10, blank=True)

    class Meta:
        verbose_name = "PyCSW Configuration"
        verbose_name_plural = "PyCSW Configuration"


class Organization(models.Model):
    name = models.CharField(max_length=255)
    short_name = models.CharField(max_length=30)
    url = models.URLField()
    address = models.CharField(max_length=255, blank=True)
    city = models.CharField(max_length=50, blank=True)
    state_or_province = models.CharField(max_length=50, blank=True)
    postal_code = models.CharField(max_length=30, blank=True)
    country = models.CharField(max_length=50, blank=True)

    def __str__(self):
        return self.short_name


class Collaborator(models.Model):
    name = models.CharField(max_length=255)
    position = models.CharField(max_length=255)
    email = models.EmailField()
    organization = models.ForeignKey(Organization, on_delete=models.PROTECT, related_name="collaborators")
    url = models.URLField(blank=True)
    phone = models.CharField(max_length=50, blank=True)
    fax = models.CharField(max_length=50, blank=True)
    hours_of_service = models.CharField(max_length=50, blank=True)
    contact_instructions = models.CharField(max_length=255, blank=True)

    def __str__(self):
        return f"{self.name} ({self.organization.short_name})"


class Tag(models.Model):
    name = models.SlugField(max_length=255, unique=True)
    description = models.TextField()

    def __str__(self):
        return self.name


def legendFilePath(instance, filename):
    id = instance.identifier.replace(":", "_").replace(" ", "_")
    ext = os.path.splitext(filename)[1]
    return f"catalogue/legends/{id}{ext}"


def sourceLegendFilePath(instance, filename):
    id = instance.identifier.replace(":", "_").replace(" ", "_")
    ext = os.path.splitext(filename)[1]
    return f"catalogue/legends/source/{id}{ext}"


class Record(models.Model):
    identifier = models.CharField(max_length=255, db_index=True, help_text="Maps to pycsw:Identifier")
    title = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        help_text="Maps to pycsw:Title",
    )
    typename = models.CharField(
        max_length=100,
        default="",
        db_index=True,
        blank=True,
        editable=False,
        help_text="Maps to pycsw:Typename",
    )
    schema = models.CharField(
        max_length=100,
        default="",
        db_index=True,
        blank=True,
        editable=False,
        help_text="Maps to pycsw:Schema",
    )
    insert_date = models.DateTimeField(auto_now_add=True, help_text="Maps to pycsw:InsertDate")
    xml = models.TextField(default="", editable=False, help_text="Maps to pycsw:XML")
    any_text = models.TextField(help_text="Maps to pycsw:AnyText", null=True, blank=True)
    modified = models.DateTimeField(auto_now=True, help_text="Maps to pycsw:Modified")
    bounding_box = models.TextField(
        null=True,
        blank=True,
        help_text="Maps to pycsw:BoundingBox. It's a WKT geometry",
    )
    abstract = models.TextField(blank=True, null=True, help_text="Maps to pycsw:Abstract")
    keywords = models.CharField(max_length=255, blank=True, null=True, help_text="Maps to pycsw:Keywords")
    tags = models.ManyToManyField(Tag, blank=True)
    publication_date = models.DateTimeField(null=True, blank=True, help_text="Maps to pycsw:PublicationDate")
    service_type = models.CharField(
        max_length=30,
        null=True,
        blank=True,
        help_text="Maps to pycsw:ServiceType",
    )
    service_type_version = models.CharField(
        max_length=30,
        null=True,
        blank=True,
        editable=False,
        help_text="Maps to pycsw:ServiceTypeVersion",
    )
    links = models.TextField(null=True, blank=True, editable=False, help_text="Maps to pycsw:Links")
    crs = models.CharField(max_length=255, null=True, blank=True, help_text="Maps to pycsw:CRS")
    active = models.BooleanField(default=True, editable=False)
    legend = models.FileField(
        upload_to=legendFilePath,
        null=True,
        blank=True,
    )
    source_legend = models.FileField(
        upload_to=sourceLegendFilePath,
        null=True,
        blank=True,
        editable=False,
    )

    bbox_re = re.compile(
        "POLYGON\s*\(\(([\+\-0-9\.]+)\s+([\+\-0-9\.]+)\s*\, \s*[\+\-0-9\.]+\s+[\+\-0-9\.]+\s*\, \s*([\+\-0-9\.]+)\s+([\+\-0-9\.]+)\s*\, \s*[\+\-0-9\.]+\s+[\+\-0-9\.]+\s*\, \s*[\+\-0-9\.]+\s+[\+\-0-9\.]+\s*\)\)"
    )

    @property
    def bbox(self):
        """
        Transform the bounding box string to bbox array
        """
        if hasattr(self, "_bbox"):
            return getattr(self, "_bbox")
        elif self.bounding_box:
            try:
                bbox = [float(v) for v in self.bbox_re.match(self.bounding_box).groups()]
                setattr(self, "_bbox", bbox)
                return bbox
            except BaseException:
                return None
        else:
            return None

    def __str__(self):
        return self.identifier

    def metadata_link(self, request):
        if request:
            return {
                "endpoint": "{}/catalogue/".format(settings.BASE_URL),
                "version": "2.0.2",
                "type": "CSW",
                "link": "{}/catalogue/?version=2.0.2&service=CSW&request=GetRecordById&elementSetName=full&typenames=csw:Record&resultType=results&id={}".format(
                    settings.BASE_URL, self.identifier
                ),
            }
        else:
            return {
                "endpoint": "{0}/catalogue/".format(settings.BASE_URL),
                "version": "2.0.2",
                "type": "CSW",
                "link": "{0}/catalogue/?version=2.0.2&service=CSW&request=GetRecordById&elementSetName=full&typenames=csw:Record&resultType=results&id={1}".format(
                    settings.BASE_URL, self.identifier
                ),
            }

    @property
    def ows_resource(self):
        """
        Get ows resource array from ows links in links column
        """
        links = self.ows_links
        resources = []
        for link in links:
            r = re.split("\t", link)
            sample_link = r[3]
            r = json.loads(r[2])
            if "WMS" in r["protocol"]:
                _type = "WMS"
            elif "WFS" in r["protocol"]:
                _type = "WFS"
            resource = {"type": _type, "version": r["version"], "endpoint": r["linkage"], "link": sample_link}
            resource.update(r)
            resources.append(resource)
        return resources

    def get_resource_links(self, _type):
        """
        Get array of links with specific type from links column
        """
        if self.links:
            links = self.links.split("^")
        else:
            links = []
        if _type == "style":
            style_links = []
            for link in links:
                r = re.split("\t", link)
                r_json = json.loads(r[2])
                if "application" in r_json["protocol"]:
                    style_links.append(link)
            links = style_links
        elif _type == "ows":
            ows_links = []
            for link in links:
                r = re.split("\t", link)
                r_json = json.loads(r[2])
                if "OGC" in r_json["protocol"]:
                    ows_links.append(link)
            links = ows_links
        return links

    @property
    def style_links(self):
        """
        Get array of style links from links column
        """
        return self.get_resource_links("style")

    @property
    def ows_links(self):
        """
        Get array of ows links from links column
        """
        return self.get_resource_links("ows")

    def generate_ows_link(self, endpoint, service_type, service_version):
        """
        Return a string ows link
        """
        if service_version in ("1.1.0", "1.1"):
            service_version = "1.1.0"
        elif service_version in ("2.0.0", "2", "2.0"):
            service_version = "2.0.0"
        elif service_version in ("1", "1.0", "1.0.0"):
            service_version = "1.0.0"

        endpoint = endpoint.strip()
        original_endpoint = endpoint
        # parse endpoint's parameters
        endpoint = endpoint.split("?", 1)
        endpoint, endpoint_parameters = (endpoint[0], endpoint[1]) if len(endpoint) == 2 else (endpoint[0], None)
        endpoint_parameters = endpoint_parameters.split("&") if endpoint_parameters else None
        endpoint_parameters = dict(
            [(p.split("=", 1)[0].upper(), p.split("=", 1)) for p in endpoint_parameters] if endpoint_parameters else []
        )

        # get target_crs
        target_crs = None
        if service_type == "WFS":
            target_crs = [endpoint_parameters.get(k)[1] for k in ["SRSNAME"] if k in endpoint_parameters]
        elif service_type in ["WMS", "GWC"]:
            target_crs = [endpoint_parameters.get(k)[1] for k in ["SRS", "CRS"] if k in endpoint_parameters]

        if target_crs:
            target_crs = target_crs[0].upper()
        else:
            target_crs = self.crs.upper() if self.crs else None

        # transform the bbox between coordinate systems, if required
        bbox = self.bbox or []
        if bbox:
            if target_crs != self.crs:
                try:
                    p1 = pyproj.Proj(init=self.crs)
                    p2 = pyproj.Proj(init=target_crs)
                    bbox[0], bbox[1] = pyproj.transform(p1, p2, bbox[0], bbox[1])
                    bbox[2], bbox[3] = pyproj.transform(p1, p2, bbox[2], bbox[3])
                except Exception as e:
                    raise ValidationError(
                        "Transform the bbox of layer({0}) from crs({1}) to crs({2}) failed.{3}".format(
                            self.identifier, self.crs, target_crs, str(e)
                        )
                    )

            if service_type == "WFS":
                # to limit the returned features, shrink the original bbox to 10 percent
                percent = 0.1

                def shrinked_min(min, max):
                    return (max - min) / 2 - (max - min) * percent / 2

                def shrinked_max(min, max):
                    return (max - min) / 2 + (max - min) * percent / 2

                shrinked_bbox = [
                    shrinked_min(bbox[0], bbox[2]),
                    shrinked_min(bbox[1], bbox[3]),
                    shrinked_max(bbox[0], bbox[2]),
                    shrinked_max(bbox[1], bbox[3]),
                ]
        else:
            shrinked_bbox = None

        def bbox2str(bbox, service, version):
            if service != "WFS" or version == "1.0.0":
                return ", ".join(str(c) for c in bbox)
            else:
                return ", ".join([str(c) for c in [bbox[1], bbox[0], bbox[3], bbox[2]]])

        if service_type == "WFS":
            kvp = {
                "SERVICE": "WFS",
                "REQUEST": "GetFeature",
                "VERSION": service_version,
            }
            parameters = {}
            if self.crs:
                kvp["SRSNAME"] = self.crs.upper()

            if target_crs:
                parameters["crs"] = target_crs

            is_geoserver = endpoint.find("geoserver") >= 0

            if service_version == "1.1.0":
                if is_geoserver:
                    kvp["maxFeatures"] = 20
                elif shrinked_bbox:
                    kvp["BBOX"] = bbox2str(shrinked_bbox, service_type, service_version)
                kvp["TYPENAME"] = self.identifier
            elif service_version == "2.0.0":
                if is_geoserver:
                    kvp["count"] = 20
                elif shrinked_bbox:
                    kvp["BBOX"] = bbox2str(shrinked_bbox, service_type, service_version)
                kvp["TYPENAMES"] = self.identifier
            else:
                if shrinked_bbox:
                    kvp["BBOX"] = bbox2str(shrinked_bbox, service_type, service_version)
                kvp["TYPENAME"] = self.identifier
        elif service_type == "WMS":
            size = self.overview_image_size
            kvp = {
                "SERVICE": "WMS",
                "REQUEST": "GetMap",
                "VERSION": service_version,
                "LAYERS": self.identifier,
                ("SRS", "CRS"): self.crs.upper(),
                "WIDTH": size[0],
                "HEIGHT": size[1],
                "FORMAT": "image/png",
            }

            parameters = {
                "crs": target_crs,
                "format": endpoint_parameters["FORMAT"][1] if "FORMAT" in endpoint_parameters else kvp["FORMAT"],
            }
            if bbox:
                kvp["BBOX"] = bbox2str(bbox, service_type, service_version)
        elif service_type == "GWC":
            service_type = "WMS"
            kvp = {
                "SERVICE": "WMS",
                "REQUEST": "GetMap",
                "VERSION": service_version,
                "LAYERS": self.identifier,
                ("SRS", "CRS"): self.crs.upper(),
                "WIDTH": 1024,
                "HEIGHT": 1024,
                "FORMAT": "image/png",
            }
            parameters = {
                "crs": target_crs,
                "format": endpoint_parameters["FORMAT"][1] if "FORMAT" in endpoint_parameters else kvp["FORMAT"],
                "width": endpoint_parameters["WIDTH"][1] if "WIDTH" in endpoint_parameters else kvp["WIDTH"],
                "height": endpoint_parameters["HEIGHT"][1] if "HEIGHT" in endpoint_parameters else kvp["HEIGHT"],
            }
            if not bbox:
                # bbox is null, use australian bbox
                bbox = [108.0000, -45.0000, 155.0000, -10.0000]
                p1 = pyproj.Proj(init="EPSG:4326")
                p2 = pyproj.Proj(init=target_crs)
                bbox[0], bbox[1] = pyproj.transform(p1, p2, bbox[0], bbox[1])
                bbox[2], bbox[3] = pyproj.transform(p1, p2, bbox[2], bbox[3])

            if not hasattr(PreviewTile, target_crs.replace(":", "_")):
                raise Exception("GWC service don't support crs({}) ".format(target_crs))

            tile_bbox = getattr(PreviewTile, target_crs.replace(":", "_"))(bbox)

            kvp["BBOX"] = bbox2str(tile_bbox, service_type, service_version)
        else:
            raise Exception("Unknown service type({})".format(service_type))

        def is_exist(k):
            return any([n.upper() in endpoint_parameters for n in (k if isinstance(k, tuple) or isinstance(k, list) else [k])])

        querystring = "&".join(
            ["{}={}".format(k[0] if isinstance(k, tuple) or isinstance(k, list) else k, v) for k, v in kvp.items() if not is_exist(k)]
        )
        if querystring:
            if original_endpoint[-1] in ("?", "&"):
                link = "{}{}".format(original_endpoint, querystring)
            elif "?" in original_endpoint:
                link = "{}&{}".format(original_endpoint, querystring)
            else:
                link = "{}?{}".format(original_endpoint, querystring)
        else:
            link = original_endpoint

        # get the endpoint after removing ows related parameters
        if endpoint_parameters:

            def is_exist(k):
                return any(
                    [
                        any([k == key.upper() for key in item_key])
                        if isinstance(item_key, tuple) or isinstance(item_key, list)
                        else k == item_key.upper()
                        for item_key in kvp
                    ]
                )

            endpoint_querystring = "&".join(["{}={}".format(*v) for k, v in endpoint_parameters.items() if not is_exist(k)])
            if endpoint_querystring:
                endpoint = "{}?{}".format(endpoint, endpoint_querystring)

        schema = {
            "protocol": "OGC:{}".format(service_type.upper()),
            "linkage": endpoint,
            "version": service_version,
        }
        schema.update(parameters)

        return "None\tNone\t{0}\t{1}".format(json.dumps(schema), link)

    def refresh_style_links(self):
        """
        Regenerate the style links if the current style links is incorrect.
        return Ture if regenerated;otherwise return False
        """
        style_links = []
        ows_links = self.ows_links

        for style in self.styles.all():
            style_links.append(Record.generate_style_link(style))

        return self.update_links(ows_links + style_links)

    @staticmethod
    def generate_style_link(style):
        """
        Return a string style link
        """
        schema = {
            "protocol": "application/{}".format(style.format.lower()),
            "name": style.name,
            "default": style.default,
            "linkage": "{}/media/".format(settings.BASE_URL),
        }
        return "None\tNone\t{0}\t{1}/media/{2}".format(json.dumps(schema, sort_keys=True), settings.BASE_URL, style.content)

    @staticmethod
    def format_links(resources):
        """
        format resources as link string
        """
        pos = 1
        links = ""
        for r in resources:
            if pos == 1:
                links += r
            else:
                links += "^{0}".format(r)
            pos += 1
        return links

    def update_links(self, resources):
        """
        update links if changed
        resources: a array of string links including ows links and style links
        return True if changed;otherwise return False
        """
        links = self.format_links(resources)
        if self.links == links:
            return False
        else:
            self.links = links
            self.save()
            return True

    @property
    def sld(self):
        """
        The default sld style file
        if not exist, return None
        """
        return self.default_style("SLD")

    @property
    def lyr(self):
        """
        The default lyr style file
        if not exist, return None
        """
        return self.default_style("LYR")

    @property
    def qml(self):
        """
        The default qml style file
        if not exist, return None
        """
        return self.default_style("QML")

    def default_style(self, format):
        try:
            return self.styles.get(format=format, default=True)
        except Style.DoesNotExist:
            return None

    """
    Used to check the default style
    for a particular format. If it does
    not exist it sets the first style as
    the default
    Return the configured default style; otherwise return None
    """

    def set_default_style(self, format):
        default_style = self.default_style(format)
        if default_style:
            return default_style
        else:
            style = None
            try:
                # no default style is configured, try to get the builtin one as the default style
                style = self.styles.get(format=format, name=Style.BUILTIN)
            except BaseException:
                # no builtin style  try to get the first added one as the default style
                style = self.styles.filter(format=format).order_by("name").first()
            if style:
                style.default = True
                setattr(style, "triggered_default_style_setting", True)
                style.save(update_fields=["default"])
                return style
            else:
                return None

    @property
    def overview_image_size(self):
        """
        Return the overview image size based on default size and bbox
        """
        default_size = (600, 600)
        if self.bbox:
            if (default_size[0] / default_size[1]) > math.fabs((self.bbox[2] - self.bbox[0]) / (self.bbox[3] - self.bbox[1])):
                return (int(default_size[1] * math.fabs((self.bbox[2] - self.bbox[0]) / (self.bbox[3] - self.bbox[1]))), default_size[1])
            else:
                return (default_size[0], int(default_size[0] * math.fabs((self.bbox[3] - self.bbox[1]) / (self.bbox[2] - self.bbox[0]))))
        else:
            return default_size

    def delete(self, using=None):
        if self.active:
            raise ValidationError("Can not delete the active record ({}).".format(self.identifier))
        else:
            super(Record, self).delete(using)

    class Meta:
        ordering = ["identifier"]


class RecordEventListener(object):
    @receiver(pre_save, sender=Record)
    def update_modify_date(sender, instance, **kwargs):
        """
        if instance.pk:
            update_fields=kwargs.get("update_fields", None)
            if not update_fields or any([f in ("title","abstract","keywords","links") for f in update_fields]):
                db_instance = Record.objects.get(pk = instance.pk)
                if any([getattr(db_instance,f) != getattr(instance,f) for f in ("title","abstract","keywords","links")]):
                    #geoserver related columns are changed, set the modified to now
                    instance.modified = timezone.now()
                    #add field "modified" into the update field list.
                    if update_fields and "modified" not in update_fields:
                        if not isinstance(update_fields,list):
                            update_fields = [f for f in update_fields]
                            kwargs["update_fields"] = update_fields
                        update_fields.append("modified")
        """
        pass


def styleFilePath(instance, filename):
    return "catalogue/styles/{}_{}.{}".format(instance.record.identifier.replace(":", "_"), instance.name, instance.format.lower())


class Style(models.Model):
    BUILTIN = "builtin"
    FORMAT_CHOICES = (("SLD", "SLD"), ("QML", "QML"), ("LYR", "LAYER"))
    record = models.ForeignKey(Record, on_delete=models.PROTECT, related_name="styles")
    name = models.CharField(max_length=255)
    format = models.CharField(max_length=3, choices=FORMAT_CHOICES)
    default = models.BooleanField(default=False)
    content = models.FileField(upload_to=styleFilePath)

    @property
    def identifier(self):
        return "{}:{}".format(self.record.identifier, self.name)

    def clean(self):
        from django.core.exceptions import ValidationError

        if not self.pk and self.name == Style.BUILTIN:
            raise ValidationError("Can't add a builtin style.")

        """
        simply reset the default style to the current style if the current style is configured as default style
        if getattr(self, "record", None) and self.default:
            try:
                duplicate = Style.objects.exclude(pk=self.pk).get(record=self.record, format=self.format, default=True)
                if duplicate and self.default:
                    raise ValidationError('There can only be one default format style for each record')
            except Style.DoesNotExist:
                pass
        """

    @property
    def can_delete(self):
        if not self.pk or self.name == Style.BUILTIN:
            return False
        return True

    def delete(self, using=None):
        if self.name == Style.BUILTIN:
            raise ValidationError("Can not delete builtin style.")
        else:
            super(Style, self).delete(using)

    def __str__(self):
        return self.name


class StyleEventListener(object):
    @staticmethod
    @receiver(post_save, sender=Style)
    def update_style_link(sender, instance, **kwargs):
        link = Record.generate_style_link(instance)
        links_parts = re.split("\t", link)
        json_link = json.loads(links_parts[2])
        style_index = -1
        style_links = instance.record.style_links
        ows_links = instance.record.ows_links
        if not instance.record.links:
            instance.record.links = ""
        index = 0
        for style_link in style_links:
            parts = re.split("\t", style_link)
            r = json.loads(parts[2])
            if r["name"] == json_link["name"] and r["protocol"] == json_link["protocol"]:
                if r["default"] != json_link["default"]:
                    style_links[index] = link
                    style_index = index
                else:
                    style_index = -2
                break
            index += 1
        if style_index == -1:
            style_links.append(link)
            links = ows_links + style_links
            instance.record.update_links(links)
        elif style_index >= 0:
            links = ows_links + style_links
            instance.record.update_links(links)

    @staticmethod
    @receiver(post_delete, sender=Style)
    def remove_style_link(sender, instance, **kwargs):
        style_links = instance.record.style_links
        ows_links = instance.record.ows_links
        # remote deleted style's link
        for link in style_links:
            parts = re.split("\t", link)
            r = json.loads(parts[2])
            if r["name"] == instance.name and instance.format.lower() in r["protocol"]:
                style_links.remove(link)

        links = ows_links + style_links
        instance.record.update_links(links)

    @staticmethod
    @receiver(pre_save, sender=Style)
    def clear_previous_default_style(sender, instance, **kwargs):
        if getattr(instance, "triggered_default_style_setting", False):
            return
        update_fields = kwargs.get("update_fields", None)
        if not instance.pk or not update_fields or "default" in update_fields:
            if instance.default:
                # The style will be set as the default style
                cur_default_style = instance.record.default_style(instance.format)
                if cur_default_style and cur_default_style.pk != instance.pk:
                    # The current default style is not the saving style, reset the current
                    # default style's default to false
                    cur_default_style.default = False
                    setattr(cur_default_style, "triggered_default_style_setting", True)
                    cur_default_style.save(update_fields=["default"])

    @staticmethod
    @receiver(post_save, sender=Style)
    def set_default_style_on_update(sender, instance, **kwargs):
        if getattr(instance, "triggered_default_style_setting", False):
            return
        update_fields = kwargs.get("update_fields", None)
        if not instance.pk or not update_fields or "default" in update_fields:
            if not instance.default:
                # The saving style is not the default style
                default_style = instance.record.default_style(instance.format)
                if not default_style:
                    instance.record.set_default_style(instance.format)

    @staticmethod
    @receiver(post_delete, sender=Style)
    def set_default_style_on_delete(sender, instance, **kwargs):
        if instance.default:
            # deleted style is the default style, reset the default style
            instance.record.set_default_style(instance.format)


class Application(models.Model):
    """
    Represent a application which can access wms, wfs, wcs service from geoserver
    """

    name = models.CharField(max_length=255, validators=[validate_slug], unique=True, blank=False)
    description = models.TextField(blank=True)
    last_modify_time = models.DateTimeField(auto_now=True, null=False)
    create_time = models.DateTimeField(auto_now_add=True, null=False)
    records = models.ManyToManyField(Record)

    @staticmethod
    def get_view_name(app):
        return "catalogue_record_{}".format(app)

    @property
    def records_view(self):
        return Application.get_view_name(self.name)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class ApplicationLayer(models.Model):
    """
    The relationship between application and layer
    """

    application = models.ForeignKey(Application, on_delete=models.PROTECT, blank=False, null=False)
    layer = models.ForeignKey(Record, on_delete=models.PROTECT, null=False, blank=False, limit_choices_to={"active": True})
    order = models.PositiveIntegerField(blank=False, null=False)

    def __str__(self):
        return "{}:{}".format(self.application.name, self.layer.identifier)

    class Meta:
        unique_together = ("application", "layer")
        ordering = ["application", "order", "layer"]
