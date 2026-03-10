"""Build the domain list for the experiment.

Creates domains.json with 5 categories:
  A: MCP-enabled domains (known to have _mcp TXT records)
  B: Popular domains (from Tranco top list)
  C: Nonexistent domains (randomly generated)
  D: Slow/unreliable domains (various TLDs)
  E: HTTPS-only, no .well-known/mcp
"""

import json
import random
import string
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import DOMAINS_FILE


def random_domain(length=12) -> str:
    """Generate a random nonexistent domain name."""
    chars = string.ascii_lowercase + string.digits
    name = "".join(random.choice(chars) for _ in range(length))
    return f"{name}.com"


def build_domain_list():
    # Category A: Known MCP-enabled domains
    # This list will grow as the ecosystem grows
    mcp_domains = [
        "korm.co",
        # Add more known MCP domains as they're discovered
    ]
    # Pad with variations to reach target count (in real experiment, discover more)
    cat_a = [{"domain": d, "category": "A"} for d in mcp_domains]

    # Category B: Popular domains (Tranco-style top list, hardcoded subset)
    popular = [
        "google.com", "facebook.com", "amazon.com", "apple.com", "microsoft.com",
        "youtube.com", "twitter.com", "instagram.com", "linkedin.com", "reddit.com",
        "wikipedia.org", "netflix.com", "github.com", "stackoverflow.com", "cloudflare.com",
        "yahoo.com", "bing.com", "twitch.tv", "discord.com", "spotify.com",
        "zoom.us", "salesforce.com", "adobe.com", "shopify.com", "dropbox.com",
        "slack.com", "notion.so", "figma.com", "vercel.com", "netlify.com",
        "heroku.com", "digitalocean.com", "stripe.com", "paypal.com", "square.com",
        "medium.com", "substack.com", "wordpress.com", "tumblr.com", "blogger.com",
        "nytimes.com", "bbc.com", "cnn.com", "reuters.com", "washingtonpost.com",
        "nasa.gov", "mit.edu", "stanford.edu", "harvard.edu", "oxford.ac.uk",
    ]
    cat_b = [{"domain": d, "category": "B"} for d in popular[:50]]

    # Category C: Nonexistent domains
    random.seed(42)  # reproducible
    cat_c = [{"domain": random_domain(), "category": "C"} for _ in range(50)]

    # Category D: Slow/unreliable (less common TLDs, typically slower resolution)
    slow_domains = [
        "example.museum", "example.travel", "nic.coop", "nic.aero",
        "registro.br", "nic.ar", "nic.cl", "nic.pe",
        "domain.gov.au", "domain.gov.uk", "nic.in", "nic.jp",
        "nic.za", "nic.ke", "nic.ng", "nic.gh",
        "nic.tz", "registry.om", "nic.qa", "nic.kw",
        "nic.ly", "nic.tn", "nic.dz", "nic.ma",
        "nic.sn", "nic.ci", "nic.cm", "nic.ga",
        "nic.tg", "nic.bj", "nic.bf", "nic.ml",
        "nic.gn", "nic.sl", "nic.lr", "nic.gm",
        "nic.cv", "nic.st", "nic.td", "nic.cf",
        "nic.cg", "nic.cd", "nic.rw", "nic.bi",
        "nic.ug", "nic.mw", "nic.zm", "nic.zw",
        "nic.bw", "nic.na",
    ]
    cat_d = [{"domain": d, "category": "D"} for d in slow_domains[:50]]

    # Category E: HTTPS-only sites (major sites that definitely serve HTTPS but no MCP)
    https_only = [
        "chase.com", "bankofamerica.com", "wellsfargo.com", "citibank.com",
        "usbank.com", "capitalone.com", "ally.com", "schwab.com",
        "fidelity.com", "vanguard.com", "tdameritrade.com", "etrade.com",
        "robinhood.com", "coinbase.com", "binance.com", "kraken.com",
        "airbnb.com", "uber.com", "lyft.com", "doordash.com",
        "grubhub.com", "instacart.com", "walmart.com", "target.com",
        "costco.com", "homedepot.com", "lowes.com", "bestbuy.com",
        "ikea.com", "wayfair.com", "ebay.com", "etsy.com",
        "wish.com", "aliexpress.com", "rakuten.com", "mercadolibre.com",
        "booking.com", "expedia.com", "tripadvisor.com", "kayak.com",
        "southwest.com", "united.com", "delta.com", "aa.com",
        "hilton.com", "marriott.com", "airbnb.com", "vrbo.com",
        "zillow.com", "redfin.com",
    ]
    cat_e = [{"domain": d, "category": "E"} for d in https_only[:50]]

    # Combine all categories
    all_domains = cat_a + cat_b + cat_c + cat_d + cat_e

    output = {
        "description": "MCP Discovery Benchmark domain list",
        "generated_seed": 42,
        "categories": {
            "A": "MCP-enabled domains (known _mcp TXT records)",
            "B": "Popular domains (Tranco-style top list)",
            "C": "Nonexistent domains (randomly generated)",
            "D": "Slow/unreliable domains (uncommon TLDs)",
            "E": "HTTPS-only sites (no MCP expected)",
        },
        "counts": {
            cat: len([d for d in all_domains if d["category"] == cat])
            for cat in "ABCDE"
        },
        "total": len(all_domains),
        "domains": all_domains,
    }

    with open(DOMAINS_FILE, "w") as f:
        json.dump(output, f, indent=2)

    print(f"Built domain list: {len(all_domains)} domains")
    for cat in "ABCDE":
        count = output["counts"][cat]
        print(f"  Category {cat}: {count} domains — {output['categories'][cat]}")


if __name__ == "__main__":
    build_domain_list()
