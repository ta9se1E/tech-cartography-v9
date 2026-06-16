"""Technology cluster domain model."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class TechnologyCluster:
  cluster_id: str
  name: str
  description: str
  representative_terms: list[str] = field(default_factory=list)
  search_intents: list[str] = field(default_factory=list)
  patent_count: int = 0
  representative_patents: list[str] = field(default_factory=list)
  top_assignees: list[str] = field(default_factory=list)
  evidence_status: str = "metadata_only"
  notes: list[str] = field(default_factory=list)

  def to_dict(self) -> dict[str, Any]:
    return asdict(self)


def default_carbon_fiber_clusters() -> list[TechnologyCluster]:
  return [
    TechnologyCluster(
      cluster_id="core_manufacturing",
      name="PAN前駆体・耐炎化・炭化プロセス",
      description="PAN precursor stabilization, oxidation, carbonization, and heat treatment.",
      representative_terms=[
        "PAN",
        "polyacrylonitrile",
        "precursor",
        "stabilization",
        "oxidation",
        "carbonization",
        "heat treatment",
        "graphitization",
      ],
      search_intents=["core_manufacturing"],
    ),
    TechnologyCluster(
      cluster_id="surface_interface",
      name="表面処理・sizing・界面接着",
      description="Surface treatment, sizing, and interface adhesion for carbon fiber.",
      representative_terms=[
        "surface treatment",
        "sizing",
        "interface adhesion",
        "interfacial",
        "resin impregnation",
        "surface functional group",
      ],
      search_intents=["surface_interface"],
    ),
    TechnologyCluster(
      cluster_id="bundle_prepreg",
      name="炭素繊維束・tow・prepreg",
      description="Fiber bundles, tow, and prepreg intermediate products.",
      representative_terms=[
        "carbon fiber bundle",
        "tow",
        "prepreg",
        "fiber bundle",
        "laminate",
      ],
      search_intents=["bundle_prepreg"],
    ),
    TechnologyCluster(
      cluster_id="application_pressure_aerospace",
      name="圧力容器・航空宇宙・複合材用途",
      description="Pressure vessel, aerospace, automotive, and composite applications.",
      representative_terms=[
        "pressure vessel",
        "aerospace",
        "composite",
        "automotive",
        "spring",
        "tank",
      ],
      search_intents=["application"],
    ),
    TechnologyCluster(
      cluster_id="property_defect_control",
      name="物性制御・欠陥抑制",
      description="Mechanical properties and defect control.",
      representative_terms=[
        "tensile strength",
        "modulus",
        "defect",
        "void",
        "density",
        "crystallite",
        "orientation",
      ],
      search_intents=[],
    ),
    TechnologyCluster(
      cluster_id="company_watch",
      name="主要企業・競合周辺出願",
      description="Patents around major carbon fiber competitors.",
      representative_terms=[
        "TORAY",
        "TEIJIN",
        "MITSUBISHI",
        "HYOSUNG",
        "ZHONGFU",
        "SGL",
        "HEXCEL",
      ],
      search_intents=["company_watch"],
    ),
    TechnologyCluster(
      cluster_id="other_related",
      name="その他関連候補",
      description="General carbon fiber related patents not strongly mapped elsewhere.",
      representative_terms=["carbon fiber", "composite material"],
      search_intents=[],
    ),
  ]
