#show: doc => article(
$if(title)$
  title: [$title$],
$endif$
$if(subtitle)$
  subtitle: [$subtitle$],
$endif$
$if(biorxiv-authors)$
  authors: (
$for(biorxiv-authors)$
    (
      name: [$it.name$],
      marks: "$it.affil-marks$".split(",").filter(m => m != ""),
      corresponding: $if(it.corresponding)$$it.corresponding$$else$false$endif$,
$if(it.email)$
      email: [$it.email$],
$endif$
    ),
$endfor$
  ),
$endif$
$if(biorxiv-affiliations)$
  affiliations: (
$for(biorxiv-affiliations)$
    (index: "$it.index$", text: [$it.text$]),
$endfor$
  ),
$endif$
$if(date)$
  date: [$date$],
$endif$
$if(lang)$
  lang: "$lang$",
$endif$
$if(region)$
  region: "$region$",
$endif$
$if(abstract)$
  abstract: [$abstract$],
  abstract-title: "$labels.abstract$",
$endif$
$if(keywords)$
  keywords: [$for(keywords)$$it$$sep$, $endfor$],
$endif$
$if(correspondence-email)$
  correspondence: [$correspondence-email$],
$elseif(correspondence)$
  correspondence: [$correspondence$],
$endif$
$if(mainfont)$
  font: ("$mainfont$",),
$elseif(brand.typography.base.family)$
  font: $brand.typography.base.family$,
$endif$
$if(fontsize)$
  fontsize: $fontsize$,
$elseif(brand.typography.base.size)$
  fontsize: $brand.typography.base.size$,
$endif$
$if(title)$
$if(brand.typography.headings.family)$
  heading-family: $brand.typography.headings.family$,
$endif$
$if(brand.typography.headings.weight)$
  heading-weight: $brand.typography.headings.weight$,
$endif$
$if(brand.typography.headings.style)$
  heading-style: "$brand.typography.headings.style$",
$endif$
$if(brand.typography.headings.color)$
  heading-color: $brand.typography.headings.color$,
$endif$
$if(brand.typography.headings.line-height)$
  heading-line-height: $brand.typography.headings.line-height$,
$endif$
$endif$
$if(section-numbering)$
  sectionnumbering: "$section-numbering$",
$endif$
$if(toc)$
  toc: $toc$,
$endif$
$if(toc-title)$
  toc_title: [$toc-title$],
$endif$
$if(toc-indent)$
  toc_indent: $toc-indent$,
$endif$
  toc_depth: $toc-depth$,
  cols: $if(columns)$$columns$$else$2$endif$,
$if(shorttitle)$
  shorttitle: [$shorttitle$],
$endif$
$if(leadauthor)$
  leadauthor: [$leadauthor$],
$endif$
  doc,
)
