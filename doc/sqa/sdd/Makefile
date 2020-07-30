LATEX_FLAGS=-interaction=nonstopmode

all: default TEAL_software_design_description.pdf

TEAL_software_design_description.pdf : TEAL_software_design_description.tex TEAL_software_design_description.bib TEALDesignStakeHoldersAndConcerns.tex TEALIntro.tex ../../version.tex TEALSoftwareDesing.tex TEALDepAndLimitations.tex otherDesignDocs.tex dataInterfaceSystemControl.tex
	pdflatex $(LATEX_FLAGS) TEAL_software_design_description.tex
	bibtex TEAL_software_design_description
	pdflatex $(LATEX_FLAGS) TEAL_software_design_description.tex
	pdflatex $(LATEX_FLAGS) TEAL_software_design_description.tex

../../version.tex : *.tex
	git log -1 --format="%H %an %aD" .. > ../../version.tex

default: *.tex

.PHONY: clean

clean:
	@rm -f *~ *.aux *.bbl *.blg *.log *.out *.toc *.lot *.lof TEAL_software_design_description.pdf dependencies.tex