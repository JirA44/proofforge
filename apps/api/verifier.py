import hashlib
import itertools
import json
import re


TOKEN = re.compile(r"\s*(->|[()!&|]|[A-Za-z_][A-Za-z0-9_]*)")


class Parser:
    def __init__(self, expression: str, variables: set[str]):
        expression = expression.strip()
        self.tokens=[]; position=0
        while position < len(expression):
            match=TOKEN.match(expression,position)
            if not match: raise ValueError(f"invalid token at position {position}")
            self.tokens.append(match.group(1)); position=match.end()
        self.position=0; self.variables=variables

    def peek(self): return self.tokens[self.position] if self.position < len(self.tokens) else None

    def take(self, token=None):
        current=self.peek()
        if current is None or (token is not None and current != token): raise ValueError(f"expected {token or 'expression'}")
        self.position+=1; return current

    def parse(self):
        node=self.implication()
        if self.peek() is not None: raise ValueError("unexpected trailing token")
        return node

    def implication(self):
        left=self.disjunction()
        if self.peek()=="->": self.take("->"); return ("implies",left,self.implication())
        return left

    def disjunction(self):
        node=self.conjunction()
        while self.peek()=="|": self.take("|"); node=("or",node,self.conjunction())
        return node

    def conjunction(self):
        node=self.negation()
        while self.peek()=="&": self.take("&"); node=("and",node,self.negation())
        return node

    def negation(self):
        if self.peek()=="!": self.take("!"); return ("not",self.negation())
        if self.peek()=="(": self.take("("); node=self.implication(); self.take(")"); return node
        variable=self.take()
        if variable not in self.variables: raise ValueError(f"undeclared variable: {variable}")
        return ("var",variable)


def evaluate(node, valuation):
    operation=node[0]
    if operation=="var": return valuation[node[1]]
    if operation=="not": return not evaluate(node[1],valuation)
    if operation=="and": return evaluate(node[1],valuation) and evaluate(node[2],valuation)
    if operation=="or": return evaluate(node[1],valuation) or evaluate(node[2],valuation)
    if operation=="implies": return (not evaluate(node[1],valuation)) or evaluate(node[2],valuation)
    raise ValueError("unknown expression node")


def canonical_hash(value) -> str:
    raw=json.dumps(value,sort_keys=True,separators=(",",":"),ensure_ascii=True)
    return hashlib.sha256(raw.encode()).hexdigest()


def verify(expression: str, variables: list[str]) -> tuple[str,int,dict[str,bool] | None,str]:
    tree=Parser(expression,set(variables)).parse(); counterexample=None; checked=0
    for values in itertools.product((False,True),repeat=len(variables)):
        valuation=dict(zip(variables,values)); checked+=1
        if not evaluate(tree,valuation): counterexample=valuation; break
    verdict="VERIFIED" if counterexample is None else "REFUTED"
    result={"expression":expression,"variables":variables,"verdict":verdict,"valuations_checked":checked,"counterexample":counterexample}
    return verdict,checked,counterexample,canonical_hash(result)


def verify_argument(
    premises: list[str], conclusion: str, variables: list[str]
) -> tuple[str, int, int, dict[str, bool] | None, str]:
    declared = set(variables)
    premise_trees = [Parser(expression, declared).parse() for expression in premises]
    conclusion_tree = Parser(conclusion, declared).parse()
    counterexample = None
    valuations_checked = 0
    premise_models = 0

    for values in itertools.product((False, True), repeat=len(variables)):
        valuation = dict(zip(variables, values))
        valuations_checked += 1
        if all(evaluate(tree, valuation) for tree in premise_trees):
            premise_models += 1
            if not evaluate(conclusion_tree, valuation):
                counterexample = valuation
                break

    if counterexample is not None:
        verdict = "NOT_ENTAILED"
    elif premise_models == 0:
        verdict = "INCONSISTENT_PREMISES"
    else:
        verdict = "ENTAILED"

    result = {
        "premises": premises,
        "conclusion": conclusion,
        "variables": variables,
        "verdict": verdict,
        "valuations_checked": valuations_checked,
        "premise_models": premise_models,
        "counterexample": counterexample,
    }
    return (
        verdict,
        valuations_checked,
        premise_models,
        counterexample,
        canonical_hash(result),
    )


def compare_formulas(
    left_expression: str, right_expression: str, variables: list[str]
) -> tuple[str, int, dict | None, str]:
    declared = set(variables)
    left_tree = Parser(left_expression, declared).parse()
    right_tree = Parser(right_expression, declared).parse()
    counterexample = None
    valuations_checked = 0

    for values in itertools.product((False, True), repeat=len(variables)):
        valuation = dict(zip(variables, values))
        valuations_checked += 1
        left_value = evaluate(left_tree, valuation)
        right_value = evaluate(right_tree, valuation)
        if left_value != right_value:
            counterexample = {
                "valuation": valuation,
                "left_value": left_value,
                "right_value": right_value,
            }
            break

    verdict = "EQUIVALENT" if counterexample is None else "NOT_EQUIVALENT"
    result = {
        "left_expression": left_expression,
        "right_expression": right_expression,
        "variables": variables,
        "verdict": verdict,
        "valuations_checked": valuations_checked,
        "counterexample": counterexample,
    }
    return verdict, valuations_checked, counterexample, canonical_hash(result)


def analyze_inconsistency(premises: list[str], variables: list[str]) -> dict:
    """Return an inclusion-minimal inconsistent core with machine witnesses."""
    declared = set(variables)
    trees = [Parser(expression, declared).parse() for expression in premises]
    valuation_space = [
        dict(zip(variables, values))
        for values in itertools.product((False, True), repeat=len(variables))
    ]
    valuations_checked = 0

    def first_model(indices: list[int]) -> dict[str, bool] | None:
        nonlocal valuations_checked
        for valuation in valuation_space:
            valuations_checked += 1
            if all(evaluate(trees[index], valuation) for index in indices):
                return valuation
        return None

    all_indices = list(range(len(premises)))
    satisfying_assignment = first_model(all_indices)
    if satisfying_assignment is not None:
        result = {
            "verdict": "CONSISTENT",
            "variables": variables,
            "premises": premises,
            "valuations_checked": valuations_checked,
            "satisfying_assignment": satisfying_assignment,
            "core_indices": [],
            "minimal_core": [],
            "necessity_witnesses": [],
            "minimality_verified": False,
        }
        result["analysis_hash"] = canonical_hash(result)
        return result

    core = all_indices.copy()
    for index in all_indices:
        if index not in core:
            continue
        candidate = [current for current in core if current != index]
        if first_model(candidate) is None:
            core = candidate

    witnesses = []
    minimality_verified = True
    for index in core:
        reduced = [current for current in core if current != index]
        witness = first_model(reduced)
        if witness is None:
            minimality_verified = False
        witnesses.append(
            {
                "removed_index": index,
                "removed_premise": premises[index],
                "valuation": witness,
            }
        )

    result = {
        "verdict": "INCONSISTENT",
        "variables": variables,
        "premises": premises,
        "valuations_checked": valuations_checked,
        "satisfying_assignment": None,
        "core_indices": core,
        "minimal_core": [premises[index] for index in core],
        "necessity_witnesses": witnesses,
        "minimality_verified": minimality_verified,
    }
    result["analysis_hash"] = canonical_hash(result)
    return result
