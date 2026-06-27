#let biorxiv_title_block(
  title: none,
  subtitle: none,
  authors: (),
  affiliations: (),
  correspondence: none,
  abstract: none,
  abstract-title: "Abstract",
  keywords: none,
) = {
  if title != none {
    text(weight: "bold", size: 16pt)[#title]
  }
  if subtitle != none {
    parbreak()
    text(size: 12pt)[#subtitle]
  }

  if authors.len() > 0 {
    parbreak()
    let author_runs = authors.map(a => {
      let marks = if a.marks == none { () } else { a.marks }
      let star = if a.corresponding { ("*",) } else { () }
      let sup = (..marks, ..star)
      if sup.len() > 0 {
        [#a.name#super(sup.join(","))]
      } else {
        [#a.name]
      }
    })
    author_runs.join([, ])
  }

  if affiliations.len() > 0 {
    parbreak()
    let aff_lines = affiliations.map(aff => super(aff.index) + h(0.25em) + aff.text)
    text(size: 9pt)[#stack(spacing: 0.3em, ..aff_lines)]
  }

  if correspondence != none {
    parbreak()
    text(size: 9pt)[*Correspondence:* #correspondence]
  }

  if abstract != none {
    parbreak()
    block(inset: (top: 0.5em, bottom: 0.5em))[
      #set text(size: 9.5pt)
      #text(weight: "bold")[#abstract-title] #h(0.75em) #abstract
    ]
  }

  if keywords != none {
    parbreak()
    text(size: 9pt)[*Keywords:* #keywords]
  }
}

#let biorxiv_wordmark() = {
  [bio#text(fill: red)[R]χiv]
}

#let article(
  title: none,
  subtitle: none,
  authors: (),
  affiliations: (),
  date: none,
  abstract: none,
  abstract-title: none,
  keywords: none,
  correspondence: none,
  cols: 2,
  shorttitle: none,
  leadauthor: none,
  lang: "en",
  region: "US",
  font: ("Libertinus Serif", "New Computer Modern"),
  fontsize: 10.5pt,
  heading-family: ("Libertinus Serif", "New Computer Modern"),
  heading-weight: "bold",
  heading-style: "normal",
  heading-color: black,
  heading-line-height: 0.65em,
  sectionnumbering: none,
  toc: false,
  toc_title: none,
  toc_depth: none,
  toc_indent: 1.5em,
  doc,
) = {
  set par(justify: true)
  set text(lang: lang, region: region, font: font, size: fontsize)
  set heading(numbering: sectionnumbering)

  let author_stub = if leadauthor != none {
    if authors.len() > 1 {
      [#leadauthor #h(0.2em)#emph[et al.]]
    } else {
      [#leadauthor]
    }
  } else {
    none
  }

  set page(
    numbering: none,
    footer: context {
      let p = counter(page).get().at(0)
      let last = counter(page).final().at(0)
      let mark = biorxiv_wordmark()
      let date_str = datetime.today().display("[month repr:long] [day], [year]")
      let sep = h(7pt) + [|] + h(7pt)
      let dash = sym.dash.en
      let author_part = if author_stub != none { author_stub + sep } else { [] }
      let footer_font = font

      if p == 1 {
        let first = author_part + mark + sep + date_str + sep + str(p) + dash + str(last)
        align(horizon, box(width: 1fr, text(font: footer_font, size: 7pt)[#first]))
      } else {
        let is_even = calc.rem(p, 2) == 0
        let title_part = if shorttitle != none { shorttitle } else { [] }

        let left_content = if is_even { str(p) + sep + mark } else { author_part + title_part }
        let right_content = if is_even { author_part + title_part } else { mark + sep + str(p) }

        grid(
          columns: (1fr, 1fr),
          column-gutter: 0pt,
          text(font: footer_font, size: 7pt)[#left_content],
          align(right, text(font: footer_font, size: 7pt)[#right_content]),
        )
      }
    }
  )

  biorxiv_title_block(
    title: title,
    subtitle: subtitle,
    authors: authors,
    affiliations: affiliations,
    correspondence: correspondence,
    abstract: abstract,
    abstract-title: abstract-title,
    keywords: keywords,
  )

  if date != none {
    parbreak()
    set text(size: 9pt)
    [#date]
  }

  if toc {
    let title = if toc_title == none { auto } else { toc_title }
    block(above: 0em, below: 1.5em)[
      outline(title: title, depth: toc_depth, indent: toc_indent);
    ]
  }

  parbreak()
  if cols <= 1 {
    doc
  } else {
    columns(cols, doc)
  }
}

#set table(inset: 6pt, stroke: none)
