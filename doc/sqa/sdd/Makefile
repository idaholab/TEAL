LATEX_FLAGS=-interaction=nonstopmode

all: default cash_flow_software_design_description.pdf

cash_flow_software_design_description.pdf : cash_flow_software_design_description.tex cash_flow_software_design_description.bib cash_flowDesignStakeHoldersAndConcerns.tex cash_flowIntro.tex ../../version.tex cash_flowSoftwareDesing.tex cash_flowDepAndLimitations.tex otherDesignDocs.tex dataInterfaceSystemControl.tex
	pdflatex $(LATEX_FLAGS) cash_flow_software_design_description.tex
	bibtex cash_flow_software_design_description
	pdflatex $(LATEX_FLAGS) cash_flow_software_design_description.tex
	pdflatex $(LATEX_FLAGS) cash_flow_software_design_description.tex

../../version.tex : *.tex
	git log -1 --format="%H %an %aD" .. > ../../version.tex

default: *.tex

.PHONY: clean

clean:
	@rm -f *~ *.aux *.bbl *.blg *.log *.out *.toc *.lot *.lof cash_flow_software_design_description.pdf dependencies.tex