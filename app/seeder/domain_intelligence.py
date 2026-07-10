"""Domain Intelligence Engine for contextual data generation."""

from typing import Any, ClassVar

import structlog

from app.schemas.schema_design import SchemaModel

logger = structlog.get_logger()


class DomainIntelligenceEngine:
    """Detects schema domain and provides industry-specific context to the LLM."""

    # Configurable domain rules
    DOMAIN_CONFIG: ClassVar[dict[str, dict[str, Any]]] = {
        "Healthcare": {
            "keywords": [
                "patient",
                "doctor",
                "prescription",
                "hospital",
                "visit",
                "diagnosis",
                "clinic",
                "medical",
            ],
            "enrichment": "Detected Domain: Healthcare\n- Generate realistic patient information and valid medical terminology.\n- Use realistic diagnosis descriptions.\n- Maintain believable appointment schedules and medical history.",
            "terminologies": [
                "Scheduled",
                "Completed",
                "Cancelled",
                "No Show",
                "Admitted",
                "Discharged",
            ],
        },
        "Banking": {
            "keywords": [
                "account",
                "transaction",
                "balance",
                "bank",
                "deposit",
                "withdrawal",
                "transfer",
                "payment",
                "loan",
                "card",
            ],
            "enrichment": "Detected Domain: Banking\n- Generate realistic financial and banking information.\n- Ensure transaction amounts and types make logical financial sense.\n- Maintain realistic currency values and standard banking statuses.",
            "terminologies": [
                "Deposit",
                "Withdrawal",
                "Transfer",
                "Payment",
                "Cleared",
                "Pending",
                "Failed",
            ],
        },
        "Retail": {
            "keywords": [
                "product",
                "order",
                "customer",
                "retail",
                "cart",
                "item",
                "inventory",
                "stock",
                "category",
            ],
            "enrichment": "Detected Domain: Retail / E-Commerce\n- Generate realistic product catalog and shopping data.\n- Ensure prices, discounts, and quantities are typical for consumer goods.\n- Use realistic shipping and fulfillment statuses.",
            "terminologies": [
                "Processing",
                "Shipped",
                "Delivered",
                "Returned",
                "In Stock",
                "Out of Stock",
            ],
        },
        "Education": {
            "keywords": [
                "student",
                "course",
                "enrollment",
                "class",
                "teacher",
                "grade",
                "university",
                "school",
                "semester",
            ],
            "enrichment": "Detected Domain: Education\n- Generate realistic academic and educational records.\n- Ensure course names, grades, and schedules reflect typical educational institutions.\n- Use valid academic terms (e.g. Fall, Spring, Pass, Fail).",
            "terminologies": [
                "Enrolled",
                "Dropped",
                "Graduated",
                "A",
                "B",
                "C",
                "Fail",
                "Pass",
            ],
        },
        "HR": {
            "keywords": [
                "employee",
                "company",
                "payroll",
                "hr",
                "salary",
                "department",
                "manager",
                "hire",
                "title",
            ],
            "enrichment": "Detected Domain: Human Resources\n- Generate realistic employment and personnel data.\n- Assign realistic job titles, departments, and corporate hierarchies.\n- Ensure salaries align with reasonable corporate pay scales.",
            "terminologies": [
                "Active",
                "Terminated",
                "On Leave",
                "Full-time",
                "Contractor",
                "Part-time",
            ],
        },
        "Manufacturing": {
            "keywords": [
                "factory",
                "machine",
                "production",
                "part",
                "assembly",
                "manufacture",
                "batch",
                "plant",
            ],
            "enrichment": "Detected Domain: Manufacturing\n- Generate realistic industrial and production data.\n- Ensure assembly lines, batches, and parts reflect manufacturing processes.\n- Maintain realistic operational states and maintenance logs.",
            "terminologies": [
                "In Production",
                "QA Passed",
                "Defective",
                "Maintenance",
                "Idle",
                "Operational",
            ],
        },
        "Blog": {
            "keywords": [
                "post",
                "comment",
                "user",
                "author",
                "article",
                "blog",
                "tag",
                "category",
                "content",
            ],
            "enrichment": "Detected Domain: Blog / CMS\n- Generate realistic content for articles and social interaction.\n- Use varied tones for comments and realistic text lengths for posts.\n- Use valid publishing statuses.",
            "terminologies": ["Draft", "Published", "Archived", "Review"],
        },
    }

    @classmethod
    def analyze(cls, schema: SchemaModel) -> dict[str, Any]:
        """Infer the domain from schema structure and return context."""
        domain_scores = {domain: 0.0 for domain in cls.DOMAIN_CONFIG}

        # Analyze table and column names
        text_corpus = []
        for table in schema.tables:
            text_corpus.append(table.name.lower())
            for col in table.columns:
                text_corpus.append(col.name.lower())

        # Count keyword hits
        for word in text_corpus:
            for domain, config in cls.DOMAIN_CONFIG.items():
                for keyword in config["keywords"]:
                    if keyword in word:
                        domain_scores[domain] += 1.0

        # Find best match
        best_domain = max(domain_scores.keys(), key=lambda k: domain_scores[k])
        max_score = domain_scores[best_domain]
        total_score = sum(domain_scores.values())

        confidence = (max_score / total_score) if total_score > 0 else 0.0

        if confidence < 0.2:
            logger.info(
                "Domain intelligence: No clear domain detected", confidence=confidence
            )
            return {"domain": "Generic", "enrichment": "", "confidence": confidence}

        logger.info(
            "Domain intelligence applied",
            domain=best_domain,
            confidence=confidence,
            score=max_score,
        )

        return {
            "domain": best_domain,
            "enrichment": cls.DOMAIN_CONFIG[best_domain]["enrichment"],
            "terminologies": cls.DOMAIN_CONFIG[best_domain]["terminologies"],
            "confidence": confidence,
        }
