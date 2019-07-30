LATEX_FLAGS=-interaction=nonstopmode

all: cash_flow_software_requirements_specifications.pdf

cash_flow_software_requirements_specifications.pdf : cash_flow_software_requirements_specifications.tex cash_flow_software_requirements_specifications.bib intro.tex ../../version.tex ../sdd/cash_flowDepAndLimitations.tex
	python readRequirementsAndCreateLatex.py -i requirements_list.xml -o requirements.tex 
	pdflatex $(LATEX_FLAGS) cash_flow_software_requirements_specifications.tex
	pdflatex $(LATEX_FLAGS) cash_flow_software_requirements_specifications.tex
	pdflatex $(LATEX_FLAGS) cash_flow_software_requirements_specifications.tex

../../version.tex : *.tex
	git log -1 --format="%H %an %aD" .. > ../../version.tex

default: *.tex

.PHONY: clean

clean:
	@rm -f *~ *.aux *.bbl *.blg *.log *.out *.toc *.lot *.lof cash_flow_software_requirements_specifications.pdf