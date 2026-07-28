# Watson Logistics — Odoo 18 Website Module

Corporate site for Watson Logistics, ported from the approved design build.

## Install
1. Copy `website_watson/` into your addons path (or add the repo to odoo.sh).
2. Restart Odoo with `-u base` or update the Apps list.
3. Apps → search **Watson Logistics Website** → Install.
   `website`, `website_blog` and `website_crm` are pulled in automatically.
4. The homepage is published at `/watson-home` and the site root is pointed at it.

## Where the content lives
Repeating content is stored in models, not markup, so nothing needs template
editing to change. Website → Configuration → **Watson Content**:

| Menu | Model | Drives |
|---|---|---|
| Services | `watson.service` | Service cards + the detail tabs |
| Branches | `watson.branch` | Branch cards (image field = QR code) |
| Team | `watson.team.member` | Team grid (initials shown until a photo is set) |
| Certifications | `watson.certification` | Accreditation logos |
| Counters | `watson.counter` | Headline figures band |
| Industries | `watson.industry` | Industries served |

Site-wide contact details (phone, mobile, WhatsApp, email, head office, socials)
are fields on the **website** record: Settings → Website → Websites → edit.

Free text — headings, intro copy — is edited inline with the Website Builder.

## Quote form
The form posts to `website_crm`, so each submission becomes a **CRM lead**
rather than an email. Assign the sales team and stage in CRM as usual; the
extra fields (Service, Country, Origin, Destination, Cargo) land in the lead's
description. Set the notification address in Website → Configuration → Settings
if you also want an email alert.

## Blog
`website_blog` handles the blog; this module only supplies styling. Create the
blog under Website → Blogs.

## Building blocks
Four reusable snippets are registered in the Builder's Structure group —
Services, Branches, Team and Counters — so the same blocks can be dropped onto
any page.

## Conventions worth knowing
* `.btn` was renamed **`.btn-watson`** so it never collides with Bootstrap.
* `.wrap` became `.container`, letting Odoo's grid own the gutters.
* The global CSS reset is scoped to `.watson-site` so it cannot reach the
  Website Builder's own UI.
* Frontend JS runs as a public widget and disables reveal animations while the
  editor is open, so a hidden block is never unselectable.

## Not carried over from the WordPress build
* The bundled-media auto-importer — Odoo serves module assets directly from
  `static/src/img/`, so there is nothing to import.
* The custom robots.txt and meta/OG layer — Odoo's own SEO panel covers this
  per page. JSON-LD can be added as a template if the structured data from the
  WordPress build is still wanted.
