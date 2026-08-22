import { Button } from "../ui/Button";
import { SearchIcon } from "./icons";

export type LabelFilter = "all" | "Positive" | "Negative" | "ERROR";

interface ResultsFilterProps {
  search: string;
  onSearchChange: (v: string) => void;
  labelFilter: LabelFilter;
  onLabelFilterChange: (v: LabelFilter) => void;
  visibleCount: number;
  totalCount: number;
}

/**
 * Filters purely within the rows already returned by this upload -- no new
 * request, no new backend capability. Kept deliberately simple (one text
 * search + one label filter) per the Phase 3C scope: this page had no
 * filtering before, so anything added has to be safe over already-loaded
 * client-side data only.
 */
export function ResultsFilter({ search, onSearchChange, labelFilter, onLabelFilterChange, visibleCount, totalCount }: ResultsFilterProps) {
  const isFiltered = search.trim() !== "" || labelFilter !== "all";

  return (
    <div className="bsr-batch-filter">
      <label className="bsr-batch-filter__search">
        <span className="bsr-visually-hidden">Search loaded results by review text</span>
        <SearchIcon aria-hidden="true" />
        <input
          type="search"
          value={search}
          onChange={(e) => onSearchChange(e.target.value)}
          placeholder="Search loaded results…"
        />
      </label>

      <label className="bsr-batch-filter__select">
        <span className="bsr-visually-hidden">Filter loaded results by label</span>
        <select value={labelFilter} onChange={(e) => onLabelFilterChange(e.target.value as LabelFilter)}>
          <option value="all">All labels</option>
          <option value="Positive">Positive</option>
          <option value="Negative">Negative</option>
          <option value="ERROR">Errored rows</option>
        </select>
      </label>

      <span className="bsr-sm bsr-batch-filter__count">
        Showing {visibleCount.toLocaleString()} of {totalCount.toLocaleString()} loaded rows
      </span>

      {isFiltered && (
        <Button
          type="button"
          variant="ghost"
          onClick={() => {
            onSearchChange("");
            onLabelFilterChange("all");
          }}
        >
          Reset filter
        </Button>
      )}
    </div>
  );
}
