# Evidence Map Synthesis

## 対象特許

- publication number: US-12565719-B2
- title: US-12565719-B2
- assignee: (unknown)
- retrieval route: manual_google_patents
- evidence level: low_fulltext_evidence
- synthesis status: ready_with_selected_papers

このEvidence Mapは、請求項と論文候補の対応を整理したものです。論文候補は技術背景の裏取り候補であり、特許主張を証明するものではありません。FTO・侵害・有効性の判断は行いません。専門家レビューが必要です。

## 1. この特許で読めたこと

- Claim Element数: 1
- paper query候補数: 10

### extracted elements by type

- material: 1
- manual claimsから 1 件のClaim Elementを抽出しました（material=1）。
- claims-based paper query候補を 10 件生成しました。
- OpenAlex候補 12 件のうち、Evidence Map向けに 5 件を選定しました。
- 代表論文候補: PAN precursor fabrication, applications and thermal stabilization process in carbon fiber production: Experimental and mathematical modelling (strong_material_process_background) — supporting evidence candidate
- 代表論文候補: Preparation, Stabilization and Carbonization of a Novel Polyacrylonitrile-Based Carbon Fiber Precursor (strong_material_process_background) — supporting evidence candidate
- 代表論文候補: Fabrication and Properties of Carbon Fibers (strong_material_process_background) — supporting evidence candidate
- Claim × Paper candidate linkを 5 件作成しました。

## 2. 論文裏取り候補

- OpenAlex candidate count: 12
- selected evidence papers: 5

### representative selected papers (supporting evidence candidate)

- PAN precursor fabrication, applications and thermal stabilization process in carbon fiber production: Experimental and mathematical modelling (bucket=strong_material_process_background, score=0.87, doi=10.1016/j.pmatsci.2019.100575, source=Progress in Materials Science, cited_by=305)
- Preparation, Stabilization and Carbonization of a Novel Polyacrylonitrile-Based Carbon Fiber Precursor (bucket=strong_material_process_background, score=0.87, doi=10.3390/polym11071150, source=Polymers, cited_by=92)
- Fabrication and Properties of Carbon Fibers (bucket=strong_material_process_background, score=0.75, doi=10.3390/ma2042369, source=Materials, cited_by=931)
- On the structural evolution of textile grade polyacrylonitrile fibers during stabilization and carbonization: Towards the manufacture of low‐cost carbon fiber (bucket=strong_material_process_background, score=0.63, doi=10.1016/j.polymdegradstab.2021.109536, source=Polymer Degradation and Stability, cited_by=54)
- Structural Evolution of Polyacrylonitrile Fibers in Stabilization and Carbonization (bucket=property_background, score=0.98, doi=10.4236/aces.2012.22032, source=Advances in Chemical Engineering and Science, cited_by=222)

## 3. Claim × Paper Candidate Map

- [material] manual claims loaded → PAN precursor fabrication, applications and thermal stabilization process in carbon fiber production: Experimental and mathematical modelling (material_process_background, low, bucket=strong_material_process_background) [弱い対応]
  - doi=10.1016/j.pmatsci.2019.100575, source=Progress in Materials Science, cited_by=305
  - caveat: 明細書・実施例が未入力のため、請求項と論文の対応は限定的な supporting evidence candidate です。 弱い対応（fallback link）です。

## 4. Evidence Gaps

- BigQuery fulltextは未取得または限定的です。Manual Routeでclaimsを利用しています。
- 明細書（description）が未入力です。材料・プロセス・数値条件の裏取り精度が限定的です。
- 実施例・測定条件が未確認です。物性数値の裏取りは不足しています。
- claims_only由来のため、論文は証明ではなく supporting evidence candidate としてのみ扱えます。

## 5. 次アクション

- descriptionをmanualで追加する（Google Patentsから明細書を貼り付け）
- 実施例・測定条件を追加する
- selected evidence papersを技術者が確認する
- OpenAlex queryの妥当性を技術者が確認する
- CN Strategic Watch候補をPDF/manualで確認する

## 6. 注意

- このEvidence Mapは、請求項と論文候補の対応を整理したものです。論文候補は技術背景の裏取り候補であり、特許主張を証明するものではありません。FTO・侵害・有効性の判断は行いません。専門家レビューが必要です。
- 論文は証明ではない
- FTO/侵害/有効性判断ではない
- 専門家レビューが必要

※ 金額情報は含みません。