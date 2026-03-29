import re

from manimlib.mobject.types.vectorized_mobject import VGroup
from manimlib.utils.color import color_to_hex
from manimlib.mobject.svg.tex_mobject import Tex
from manimlib.mobject.geometry import RoundedRectangle
from manimlib.utils.typst_tex_symbol_count import ACCENT_COMMANDS, OPERATORS
from manimlib.utils.typst_tex_symbol_count import TYPST_TEX_SYMBOL_COUNT, DELIMITER_COMMANDS
from manimlib.utils.tex_file_writing import typst_latex2svg
from manimlib.logger import log


class TypstTex(Tex):
    # NOTE: To render fraction, kindly use `frac(a, b)` instead of `a/b` for proper indexing.
    tex_environment: str = "$"

    def __init__(
        self, *tex_strings: str, alignment: str = "center", fill_border_width: int = 0, **kwargs
    ):
        alignment = f"#set align({alignment})"
        super().__init__(
            *tex_strings, alignment=alignment, fill_border_width=fill_border_width, **kwargs
        )

        # horizontal line has no fill.
        for mob in self.family_members_with_points():
            if not mob.get_fill_opacity():
                rect = RoundedRectangle(width=mob.get_width(), height=0.025, corner_radius=0.01)
                rect.set_fill(mob.get_color(), 1).set_stroke(width=0).move_to(mob)
                mob.become(rect)
        self.set_symbol_count()

    @staticmethod
    def get_color_command(rgb_hex: str) -> str:
        return f'#text(fill: rgb("{rgb_hex}"))'

    def get_command_string(
        self, attr_dict: dict[str, str], is_end: bool, label_hex: str | None
    ) -> str:
        if label_hex is None:
            return ""
        if is_end:
            return f"{self.tex_environment}]"
        return self.get_color_command(label_hex) + f"[{self.tex_environment}"

    def get_content_prefix_and_suffix(self, is_labelled: bool) -> tuple[str, str]:
        prefix_lines = []
        suffix_line = ""

        if not is_labelled:
            prefix_lines.append(self.get_color_command(color_to_hex(self.base_color)))
        if self.alignment:
            prefix_lines.append(self.alignment)

        prefix_lines = "".join([line + "\n" for line in prefix_lines])

        if self.tex_environment:
            prefix_lines += f"{self.tex_environment} "
            suffix_line = f" {self.tex_environment}"

        return prefix_lines, suffix_line

    def get_svg_string_by_content(self, content: str) -> str:
        return typst_latex2svg(content, self.template, self.additional_preamble)

    def set_symbol_count(self):
        operators = "|".join(re.escape(op) for op in OPERATORS)
        pattern = rf"""
            (?P<txt>"[^"]*")|
            (?P<cmd>[a-zA-Z][a-zA-Z0-9\.]*[a-zA-Z0-9])|
            (?P<script>[_^])|
            (?P<operator>{operators})|
            (?P<fraction>\bfrac\b)|
            (?P<root>\broot\b)|
            (?P<char>\S)
        """

        counts = [0] * len(self.string)
        group_stack = []
        current_group = "normal"

        for match in re.finditer(pattern, self.string, re.VERBOSE):
            text = match.group()
            start = match.start()
            num = TYPST_TEX_SYMBOL_COUNT.get(text, 1)

            if match.group("txt"):
                num = len(text.replace('"', "").replace(" ", ""))
                counts[start] += num
                continue

            elif text == "(":
                group_stack.append(current_group)
                to_hide = current_group != "normal"
                current_group = "normal"
                if to_hide:
                    continue

            elif text == ")":
                if group_stack:
                    if (group := group_stack.pop()) != "normal":
                        if group in ("frac", "delimiter"):
                            counts[start] += 1
                        continue

            elif text == ",":
                if group_stack and group_stack[-1] in ("frac", "root"):
                    counts[start] += TYPST_TEX_SYMBOL_COUNT.get(group_stack[-1], 0)
                    continue

            elif text in ("frac", "root"):
                current_group = text
                continue

            elif match.group("script") or (match.group("cmd") and num == 0):
                current_group = "wrapper"
                continue

            elif text in ACCENT_COMMANDS:
                current_group = "wrapper"

            elif current_group in DELIMITER_COMMANDS:
                current_group = "delimiter"

            else:
                current_group = "normal"

            counts[start] += num if match.group("cmd") else 1
        if sum(counts) != len(self):
            log.warning(f"Estimated size of {self.get_tex()} does not match true size")
        self.symbol_count = counts

    def get_symbol_substrings(self):
        pattern = "|".join(
            (
                r"[a-zA-Z](?:[a-zA-Z0-9\.]*[a-zA-Z0-9])?",
                r"->|=>|<=|>=|==|!=|\.\.\.",
                r"[0-9]+",
                r"[^\^\{\}\s\_\$\&\\\"]",
            )
        )
        return re.findall(pattern, self.string)

    # TransformMatchingTex uses this function
    def substr_to_path_count(self, substr: str) -> int:
        return TYPST_TEX_SYMBOL_COUNT.get(substr, 1)

    def select_unisolated_substring(self, pattern: str | re.Pattern) -> VGroup:
        counts = self.symbol_count
        if isinstance(pattern, re.Pattern):
            matches = pattern.finditer(self.string)
        else:
            escape_pat = re.escape(pattern)
            if pattern[0].isalnum():
                escape_pat = r"(?<![a-zA-Z0-9_])" + escape_pat

            if pattern[-1].isalnum():
                escape_pat = escape_pat + r"(?![a-zA-Z0-9_])"

            matches = re.finditer(escape_pat, self.string)

        result = []
        for match in matches:
            start, end = match.start(), match.end()
            start_idx = sum(counts[:start])
            end_idx = start_idx + sum(counts[start:end])
            result.append(self[start_idx:end_idx])

        return VGroup(*result)


class TypstTexText(TypstTex):
    tex_environment: str = ""

    def set_symbol_count(self):
        pattern = r"""
            (?P<escape_char>\\[\S])|
            (?P<char>\S)
        """
        counts = [0] * len(self.string)
        for match in re.finditer(pattern, self.string, re.VERBOSE):
            start = match.start()
            if match.group("escape_char"):
                counts[start + 1] = 1
            else:
                counts[start] = 1

        self.symbol_count = counts
