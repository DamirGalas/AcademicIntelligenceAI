# Assumed Student Questions

Two sets of questions for different purposes:
- **Part 1 (30 questions)** — typical questions the system must handle in production
- **Part 2 (10 questions)** — hard questions for RAG stress-testing and evaluation

These are **assumptions** — not validated with real student data.

**Status:** Unvalidated. To be replaced or supplemented with real questions from:
- Student service email logs (ideal)
- Reddit / Facebook groups
- Feedback collected after pilot deployment

---

## Admissions — Prospective Students (high priority)

1. Koji studijski programi postoje na PMF-u?
2. Koji su uslovi za upis na informatiku?
3. Da li postoji prijemni ispit i iz čega se polaže?
4. Koliko studenata se prima na budžet na matematici?
5. Ko je oslobođen polaganja prijemnog ispita?
6. Kada je prijemni ispit i gde se prijavljujem?
7. Koliko bodova treba da se položi prijemni ispit iz hemije?
8. Koji dokumenti su potrebni za upis?
9. Kolika je školarina za samofinansirajuće studente?
10. Da li mogu da upišem PMF ako nisam iz Novog Sada?

---

## Study Programs — Prospective & Current Students

11. Koliko traju osnovne studije informatike?
12. Koji predmeti su na prvoj godini matematike?
13. Postoji li master studijski program iz bioinformatike?
14. Koliko ESPB bodova treba da skupim za upis sledeće godine?
15. Gde mogu da pronađem informacije o studijskom programu fizike?
16. Da li PMF ima doktorske studije i koji su uslovi?
17. Mogu li upisati master na PMF-u ako sam završio drugi fakultet?

---

## Exams & Schedules — Current Students

18. Kada su ispitni rokovi u zimskom semestru?
19. Kako se prijavljuje ispit?
20. Koliko puta mogu da polažem isti ispit?
21. Gde mogu da pronađem raspored ispita za moj studijski program?
22. Šta je uslovni ispit i kako funkcioniše?
23. Do kada mogu da odjavim ispit bez posledica?

---

## Administration — Current Students

24. Koji je email studentske službe za informatiku?
25. Kako se traži overavanje semestra?
26. Kako mogu da promenim studijski program?
27. Gde se predaju dokumenti za upis u narednu godinu?
28. Kako funkcioniše prelaz sa budžeta na samofinansiranje i obrnuto?

---

## Practical / Life at Faculty

29. Da li PMF ima studentski dom ili organizuje smeštaj?
30. Postoje li stipendije za studente PMF-a i ko ih dodeljuje?

---

## Part 2 — Hard Questions for RAG Evaluation

These test where RAG systems typically fail: multi-document retrieval,
rule interpretation, implicit information, and semantic reasoning.

31. Završio sam srednju školu sa prosekom 5.00 i bio sam na republičkom takmičenju iz matematike. Da li moram da polažem prijemni ispit?
    *Type: multi-document reasoning | Difficulty: hard*

32. Upisao sam informatiku, ali me zanima i statistika. Da li mogu da slušam neke predmete sa matematike?
    *Type: rule interpretation | Difficulty: hard*

33. Položio sam samo 3 ispita u prvoj godini. Da li mogu da upišem drugu godinu ili moram da obnavljam?
    *Type: rule interpretation | Difficulty: hard*

34. Studiram informatiku na drugom fakultetu. Da li mogu da pređem na PMF i da li mi se priznaju položeni ispiti?
    *Type: multi-document reasoning | Difficulty: hard*

35. Ako sam prve godine bio na budžetu, ali nisam položio dovoljno ispita, da li mogu da izgubim budžet?
    *Type: rule interpretation | Difficulty: hard*

36. Koja je razlika između smerova Računarske nauke i Informatika na PMF-u?
    *Type: multi-document aggregation | Difficulty: hard*

37. Radim full-time posao. Da li postoji mogućnost vanrednog studiranja na PMF-u?
    *Type: implicit information | Difficulty: hard*

38. Završio sam osnovne studije informatike na FTN-u. Da li mogu da upišem master na PMF-u?
    *Type: multi-document reasoning | Difficulty: hard*

39. Da li PMF ima parking za studente?
    *Type: unanswerable | Difficulty: hard — tests whether system hallucinates or correctly says "no information"*

40. Ako želim karijeru u data science-u, koji smer na PMF-u je najbliži tome?
    *Type: semantic recommendation | Difficulty: hard*
