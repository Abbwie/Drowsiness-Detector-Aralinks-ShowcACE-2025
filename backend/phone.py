"""Put a phone number into the form WhatsApp will accept.

Someone typing their own number writes it the way they say it -- 0967 009 2434
-- while the detector has to hand WhatsApp an international number or the
message goes nowhere at all. Normalising on the way in lets the driver type
what is natural and still end up with a number that works, and because the
response carries the stored value back, the settings page shows them what was
actually kept rather than what they typed.
"""

DEFAULT_COUNTRY_CODE = "63"         # Philippines


def normalise_phone(raw, country_code=DEFAULT_COUNTRY_CODE):
    """Return `raw` as +<country><subscriber>, or unchanged if unrecognised.

    Deliberately conservative. A number in a shape this does not recognise is
    left exactly as typed rather than guessed at: a contact that merely looks
    odd can still be corrected by hand, while one silently rewritten into a
    different real number cannot -- and the person who gets that message has
    no idea why.

        0967 009 2434   -> +639670092434
        09670092434     -> +639670092434
        +63 967 009 24  -> +63967009 24   (punctuation dropped, digits kept)
        639670092434    -> +639670092434
        0063967009243   -> +63967009243   (00 is the old way of writing +)
    """
    if raw is None:
        return ""
    text = raw.strip()
    if not text:
        return ""

    digits = "".join(ch for ch in text if ch.isdigit())
    if not digits:
        return text                         # nothing numeric; leave it be

    if text.startswith("+"):
        return "+" + digits                 # already international
    if digits.startswith("00"):
        return "+" + digits[2:]
    if digits.startswith("0"):
        # The national trunk prefix. Dropping it and prepending the country
        # code is the whole point of this function.
        return "+" + country_code + digits[1:]
    if digits.startswith(country_code):
        return "+" + digits
    return text                             # unrecognised shape, keep as typed
