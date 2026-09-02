from pathlib import Path
from typing import Dict, Any, Optional
from src.config import config

def generate_xmp_sidecar(
    xmp_path: Path,
    attendee: Dict[str, Any],
    session_num: int = 1,
    photographer_name: str = "Tanner Scholten Photography",
    gps_info: Optional[Dict[str, Any]] = None
) -> None:
    """
    Generates a standard Adobe XMP sidecar containing IPTC, Dublin Core, and EXIF GPS metadata.
    """
    full_name = f"{attendee.get('first_name', '')} {attendee.get('last_name', '')}".strip()
    email = attendee.get("email", "")
    org = attendee.get("organization", "")
    title = attendee.get("title", "")
    att_id = attendee.get("id", 1000)

    headline = full_name
    caption = f"Headshot portrait of {full_name}"
    if title or org:
        caption += f" - {title}" if title else ""
        caption += f", {org}" if org else ""

    # Check GPS configuration
    gps = gps_info or config.gps_config
    gps_xml = ""
    if gps and gps.get("enabled", False):
        lat = gps.get("latitude", "39,58.2710N")
        lon = gps.get("longitude", "83,0.1016W")
        alt = gps.get("altitude", 235)
        gps_xml = f"""\n   exif:GPSVersionID="2.2.0.0"
   exif:GPSLatitude="{lat}"
   exif:GPSLongitude="{lon}"
   exif:GPSAltitudeRef="0"
   exif:GPSAltitude="{alt}/1" """

    xmp_content = f"""<?xpacket begin="\ufeff" id="W5M0MpCehiHzreSzNTczkc9d"?>
<x:xmpmeta xmlns:x="adobe:ns:meta/" x:xmptk="Adobe XMP Core 7.0-c000 1.000000">
 <rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">
  <rdf:Description rdf:about=""
    xmlns:dc="http://purl.org/dc/elements/1.1/"
    xmlns:photoshop="http://ns.adobe.com/photoshop/1.0/"
    xmlns:Iptc4xmpCore="http://iptc.org/std/Iptc4xmpCore/1.0/xmlns/"
    xmlns:xmp="http://ns.adobe.com/xap/1.0/"
    xmlns:exif="http://ns.adobe.com/exif/1.0/"{gps_xml}>
   <dc:creator>
    <rdf:Seq>
     <rdf:li>{photographer_name}</rdf:li>
    </rdf:Seq>
   </dc:creator>
   <photoshop:Headline>{headline}</photoshop:Headline>
   <photoshop:AuthorsPosition>{photographer_name}</photoshop:AuthorsPosition>
   <Iptc4xmpCore:CreatorContactInfo
    Iptc4xmpCore:CiEmailWork="{email}"/>
   <xmp:JobRef>
    <rdf:Bag>
     <rdf:li>Attendee_{att_id}_Session_{session_num}</rdf:li>
    </rdf:Bag>
   </xmp:JobRef>
  </rdf:Description>
 </rdf:RDF>
</x:xmpmeta>
<?xpacket end="w"?>"""

    xmp_path.parent.mkdir(parents=True, exist_ok=True)
    with open(xmp_path, "w", encoding="utf-8") as f:
        f.write(xmp_content)
