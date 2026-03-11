"""Tests for GEDCOM rekey and redirect matching helpers."""

from rhodesli_ml.importers.gedcom_matching import (
    build_individual_match_profile,
    detect_individual_redirects,
    resolve_redirect_chain,
    score_individual_match,
)


def _person_payload(
    *,
    gedcom_id: str,
    name: str,
    given_name: str,
    surname: str,
    gender: str = "U",
    birth_year: int | None = None,
    death_year: int | None = None,
    birth_place: str | None = None,
    death_place: str | None = None,
    names_json: list[dict] | None = None,
) -> dict:
    birth_event_json = None
    if birth_year:
        birth_event_json = {"date": {"year": birth_year}, "raw_date": str(birth_year), "place": birth_place}

    death_event_json = None
    if death_year:
        death_event_json = {"date": {"year": death_year}, "raw_date": str(death_year), "place": death_place}

    return {
        "gedcom_id": gedcom_id,
        "name": name,
        "given_name": given_name,
        "surname": surname,
        "gender": gender,
        "birth_date": str(birth_year) if birth_year else None,
        "death_date": str(death_year) if death_year else None,
        "birth_place": birth_place,
        "death_place": death_place,
        "birth_event_json": birth_event_json,
        "death_event_json": death_event_json,
        "names_json": names_json or [],
    }


class TestBuildIndividualMatchProfile:
    def test_includes_alternate_names_and_years(self):
        payload = _person_payload(
            gedcom_id="@I1@",
            name="Leon Capeluto",
            given_name="Leon",
            surname="Capeluto",
            gender="M",
            birth_year=1905,
            death_year=1988,
            birth_place="Rhodes, Greece",
            names_json=[{"full_name": "Leonardo Capeluto", "given_name": "Leonardo", "surname": "Capeluto"}],
        )

        profile = build_individual_match_profile(payload)

        assert profile["birth_year"] == 1905
        assert profile["death_year"] == 1988
        assert "leon capeluto" in profile["name_variants"]
        assert "leonardo capeluto" in profile["name_variants"]


class TestScoreIndividualMatch:
    def test_high_score_for_rekeyed_same_person(self):
        old_payload = _person_payload(
            gedcom_id="@IOLD@",
            name="Nace Capeluto",
            given_name="Nace",
            surname="Capeluto",
            gender="M",
            birth_year=1915,
            death_year=1992,
            birth_place="Rhodes",
        )
        new_payload = _person_payload(
            gedcom_id="@INEW@",
            name="Nace Capeluto",
            given_name="Nace",
            surname="Capeluto",
            gender="M",
            birth_year=1915,
            death_year=1992,
            birth_place="Rhodes, Greece",
        )

        result = score_individual_match(old_payload, new_payload)

        assert result["score"] >= 0.75
        assert "primary_name_exact" in result["reasons"]
        assert "birth_year_exact" in result["reasons"]

    def test_zero_score_for_gender_conflict(self):
        old_payload = _person_payload(
            gedcom_id="@IOLD@",
            name="Rachel Capeluto",
            given_name="Rachel",
            surname="Capeluto",
            gender="F",
            birth_year=1912,
        )
        new_payload = _person_payload(
            gedcom_id="@INEW@",
            name="Rachel Capeluto",
            given_name="Rachel",
            surname="Capeluto",
            gender="M",
            birth_year=1912,
        )

        result = score_individual_match(old_payload, new_payload)

        assert result["score"] == 0.0
        assert result["reasons"] == ["gender_conflict"]


class TestDetectIndividualRedirects:
    def test_detects_rekey_redirect(self):
        removed_items = [
            {
                "entity_id": "@IOLD@",
                "old_payload": _person_payload(
                    gedcom_id="@IOLD@",
                    name="Nolan Fox",
                    given_name="Nolan",
                    surname="Fox",
                    gender="M",
                    birth_year=1985,
                    birth_place="Clearwater, Florida, USA",
                ),
            }
        ]
        new_map = {
            "@INEW@": _person_payload(
                gedcom_id="@INEW@",
                name="Nolan Fox",
                given_name="Nolan",
                surname="Fox",
                gender="M",
                birth_year=1985,
                birth_place="Clearwater, Pinellas, Florida, USA",
            )
        }

        redirects = detect_individual_redirects(removed_items, new_map, old_map={"@IOLD@": removed_items[0]["old_payload"]})

        assert len(redirects) == 1
        assert redirects[0]["old_key"] == "@IOLD@"
        assert redirects[0]["new_key"] == "@INEW@"
        assert redirects[0]["redirect_type"] == "rekey_redirect"

    def test_detects_merge_redirect_to_existing_key(self):
        removed_items = [
            {
                "entity_id": "@IOLD@",
                "old_payload": _person_payload(
                    gedcom_id="@IOLD@",
                    name="Leon Capeluto",
                    given_name="Leon",
                    surname="Capeluto",
                    gender="M",
                    birth_year=1905,
                    death_year=1988,
                ),
            }
        ]
        new_map = {
            "@IMERGED@": _person_payload(
                gedcom_id="@IMERGED@",
                name="Leon Capeluto",
                given_name="Leon",
                surname="Capeluto",
                gender="M",
                birth_year=1905,
                death_year=1988,
                names_json=[{"full_name": "Leonardo Capeluto", "given_name": "Leonardo", "surname": "Capeluto"}],
            )
        }
        old_map = {"@IOLD@": removed_items[0]["old_payload"], "@IMERGED@": new_map["@IMERGED@"]}

        redirects = detect_individual_redirects(removed_items, new_map, old_map=old_map)

        assert len(redirects) == 1
        assert redirects[0]["redirect_type"] == "merge_redirect"


class TestResolveRedirectChain:
    def test_resolves_multi_hop_chain(self):
        redirect_map = {"@I1@": "@I2@", "@I2@": "@I3@"}
        assert resolve_redirect_chain("@I1@", redirect_map) == "@I3@"

    def test_breaks_cycles(self):
        redirect_map = {"@I1@": "@I2@", "@I2@": "@I1@"}
        assert resolve_redirect_chain("@I1@", redirect_map) == "@I2@"
